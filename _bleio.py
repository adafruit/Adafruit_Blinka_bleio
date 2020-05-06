# The MIT License (MIT)
#
# Copyright (c) 2020 Scott Shawcroft for Adafruit Industries LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`_bleio`
================================================================================

`_bleio` for Blinka based on ``bleak``


* Author(s): Scott Shawcroft

"""

import asyncio
import os
import signal
import struct
import subprocess
import time

# Don't import bleak is we're running in the CI. We could mock it out but that
# would require mocking in all reverse dependencies.
if "GITHUB_ACTION" not in os.environ and "READTHEDOCS" not in os.environ:
    # This will only work on Linux
    from bleak.backends.bluezdbus import utils
    from txdbus import client
    from twisted.internet.asyncioreactor import AsyncioSelectorReactor
else:
    bleak = None  # pylint: disable=invalid-name
    utils = None  # pylint: disable=invalid-name

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"


class BluetoothError(Exception):
    """Catch-all exception for Bluetooth related errors."""


class ConnectionError(BluetoothError):  # pylint: disable=redefined-builtin
    """Raised when a connection is unavailable."""


class RoleError(BluetoothError):
    """
    Raised when a resource is used in a mismatched role. For example,
    will be raised if you attempt to set a local CCCD
    that can only be set when remote.
    """


class SecurityError(BluetoothError):
    """Raised when a security related error occurs."""


class Address:
    """Create a new Address object encapsulating the address value."""

    # pylint: disable=too-few-public-methods

    PUBLIC = 0x0
    RANDOM_STATIC = 0x1
    RANDOM_PRIVATE_RESOLVABLE = 0x2
    RANDOM_PRIVATE_NON_RESOLVABLE = 0x3

    def __init__(self, address, address_type=RANDOM_STATIC):
        if isinstance(address, bytes):
            self.address_bytes = address
        elif isinstance(address, str):
            address = address.split(":")
            self.address_bytes = bytes(reversed([int(x, 16) for x in address]))
        self.type = address_type


class ScanEntry:
    """Should not be instantiated directly. Use `_bleio.Adapter.start_scan`."""

    def __init__(self, event_type, address, rssi, data):
        self._data_dict = self._decode_data(data)
        # print(self._data_dict)
        self.address = address
        self.rssi = rssi
        self.advertisement_bytes = data
        self.connectable = event_type < 0x2
        self.scan_response = event_type == 0x4

    @staticmethod
    def _decode_data(data, *, key_encoding="B"):
        """Helper which decodes length encoded structures into a dictionary with the given key
           encoding."""
        i = 0
        data_dict = {}
        key_size = struct.calcsize(key_encoding)
        while i < len(data):
            item_length = data[i]
            i += 1
            if item_length == 0:
                break
            key = struct.unpack_from(key_encoding, data, i)[0]
            value = data[i + key_size : i + item_length]
            if key in data_dict:
                if not isinstance(data_dict[key], list):
                    data_dict[key] = [data_dict[key]]
                data_dict[key].append(value)
            else:
                data_dict[key] = value
            i += item_length
        return data_dict

    def matches(self, prefixes, *, all=True):
        """Returns True if the ScanEntry matches all prefixes when ``all`` is True. This is
           stricter than the scan filtering which accepts any advertisements that match any of the
           prefixes where all is False."""
        # The CircuitPython api already has an `all` parameter so we have to use it here and disable
        # the related PyLint check.
        # pylint: disable=redefined-builtin
        i = 0
        while i < len(prefixes):
            prefix_len = prefixes[i]
            i += 1
            adt = prefixes[i]
            if adt in self._data_dict:
                field = self._data_dict[adt]
                if not isinstance(field, list):
                    field = [field]
                found = False
                for value in field:
                    if value.startswith(prefixes[i + 1 : i + prefix_len - 1]):
                        found = True
                        break

                if not all and found:
                    return True
                if all and not found:
                    return False
            elif all:
                return False
            i += prefix_len
        return all


class Adapter:
    """The Adapter manages the discovery and connection to other nearby Bluetooth Low Energy
       devices. This part of the Bluetooth Low Energy Specification is known as Generic Access
       Profile (GAP).

       Discovery of other devices happens during a scanning process that listens for small packets
       of information, known as advertisements, that are broadcast unencrypted. The advertising
       packets have two different uses. The first is to broadcast a small piece of data to anyone
       who cares and and nothing more. These are known as Beacons. The second class of advertisement
       is to promote additional functionality available after the devices establish a connection.
       For example, a BLE keyboard may advertise that it can provide key information, but not what
       the key info is.

       The built-in BLE adapter can do both parts of this process: it can scan for other device
       advertisements and it can advertise its own data. Furthermore, Adapters can accept incoming
       connections and also initiate connections."""

    def __init__(self, address):
        self.address = Address(address)
        self._hcitool = None

    @staticmethod
    def _parse_buffered(buffered, prefixes, minimum_rssi, active):
        # > is controller to host, 04 is for an HCI Event packet, and 3E is an LE meta-event
        if buffered[0].startswith(b"> 04 3E"):
            subevent_code = int(buffered[0][11:13], 16)
            if subevent_code == 0x02:
                num_reports = int(buffered[0][14:16], 16)
                if num_reports > 1:
                    raise NotImplementedError("Multiple packed reports")
                # Parse RSSI first so we can filter on it.
                rssi = int(buffered[-1][-4:-2], 16)
                if rssi > 127:
                    rssi = (256 - rssi) * -1
                if rssi == 127 or rssi < minimum_rssi:
                    return None
                event_type = int(buffered[0][17:19], 16)
                # Filter out scan responses if we weren't supposed to active scan.
                if event_type == 0x04 and not active:
                    return None
                address_type = int(buffered[0][20:22], 16)
                address = bytes.fromhex(buffered[0][23:40].decode("utf-8"))
                # Mod the address type by two because 2 and 3 are resolved versions of public and
                # random static.
                address = Address(address, address_type % 2)

                buffered[0] = buffered[0][43:]
                buffered[-1] = buffered[-1][:-4]
                data = bytes.fromhex("".join([x.decode("utf-8") for x in buffered]))

                scan_entry = ScanEntry(event_type, address, rssi, data)
                if scan_entry.matches(prefixes, all=False):
                    return scan_entry
        return None

    def start_scan(
        self,
        prefixes=b"",
        *,
        buffer_size=512,
        extended=False,
        timeout=0.1,
        interval=0.1,
        window=None,
        minimum_rssi=-80,
        active=True
    ):
        """Starts a BLE scan and returns an iterator of results. Advertisements and scan responses
           are filtered and returned separately.

           :param sequence prefixes: Sequence of byte string prefixes to filter advertising packets
               with. A packet without an advertising structure that matches one of the prefixes is
               ignored. Format is one byte for length (n) and n bytes of prefix and can be repeated.
           :param int buffer_size: the maximum number of advertising bytes to buffer.
           :param bool extended: When True, support extended advertising packets. Increasing
               buffer_size is recommended when this is set.
           :param float timeout: the scan timeout in seconds. If None, will scan until `stop_scan`
               is called.
           :param float interval: the interval (in seconds) between the start of two consecutive
               scan windows.  Must be in the range 0.0025 - 40.959375 seconds.
           :param float window: the duration (in seconds) to scan a single BLE channel. window must
               be <= interval.
           :param int minimum_rssi: the minimum rssi of entries to return.
           :param bool active: retrieve scan responses for scannable advertisements.
           :returns: an iterable of `_bleio.ScanEntry` objects
           :rtype: iterable
           """
        # pylint: disable=unused-argument,too-many-locals
        hcidump = subprocess.Popen(
            ["hcidump", "--raw", "hci"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        if not self._hcitool:
            self._hcitool = subprocess.Popen(
                ["hcitool", "lescan", "--duplicates"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        # Throw away the first two output lines of hcidump because they are version info.
        hcidump.stdout.readline()
        hcidump.stdout.readline()
        returncode = self._hcitool.poll()
        start_time = time.monotonic()
        buffered = []
        while returncode is None and (
            not timeout or time.monotonic() - start_time < timeout
        ):
            line = hcidump.stdout.readline()
            # print(line, line[0])
            if line[0] != 32:  # 32 is ascii for space
                if buffered:
                    parsed = self._parse_buffered(
                        buffered, prefixes, minimum_rssi, active
                    )
                    if parsed:
                        yield parsed
                    buffered.clear()
            buffered.append(line)
            returncode = self._hcitool.poll()
        self.stop_scan()

    def stop_scan(self):
        """Stop the current scan."""
        # This does nothing for now because the scan isn't actually ongoing.
        if self._hcitool:
            if self._hcitool.returncode is None:
                self._hcitool.send_signal(signal.SIGINT)
                self._hcitool.wait()
            self._hcitool = None

    def __del__(self):
        self.stop_scan()


class Attribute:
    """Definitions associated with all BLE attributes: characteristics, descriptors, etc.

       You cannot create an instance of :py:class:`~_bleio.Attribute`."""

    # pylint: disable=too-few-public-methods

    NO_ACCESS = 0
    """security mode: access not allowed"""

    OPEN = 0
    """security_mode: no security (link is not encrypted)"""

    ENCRYPT_NO_MITM = 0
    """security_mode: unauthenticated encryption, without man-in-the-middle protection"""

    ENCRYPT_WITH_MITM = 0
    """security_mode: authenticated encryption, with man-in-the-middle protection"""

    LESC_ENCRYPT_WITH_MITM = 0
    """security_mode: LESC encryption, with man-in-the-middle protection"""

    SIGNED_NO_MITM = 0
    """security_mode: unauthenticated data signing, without man-in-the-middle protection"""

    SIGNED_WITH_MITM = 0
    """security_mode: authenticated data signing, without man-in-the-middle protection"""


class UUID:
    """A 16-bit or 128-bit UUID. Can be used for services, characteristics, descriptors and more."""

    # pylint: disable=too-few-public-methods

    def __init__(self, uuid):
        # pylint: disable=unused-argument
        # Stub out UUID
        self.size = 128
        self.uuid128 = b"\x00" * (128 // 8)

    def pack_into(self, buffer, offset=0):
        """Packs the UUID into the buffer at the given offset."""
        if len(buffer) - offset >= self.size // 8:
            for byte_position in range(self.size // 8):
                buffer[offset + byte_position] = self.uuid128[byte_position]
        else:
            raise IndexError(
                "Buffer size too small or offset is too close to the end of the buffer"
            )


class Descriptor:
    """There is no regular constructor for a Descriptor. A new local Descriptor can be created
       and attached to a Characteristic by calling `add_to_characteristic()`. Remote Descriptor
       objects are created by ``Connection.discover_remote_services()`` as part of remote
       Characteristics in the remote Services that are discovered."""

    # pylint: disable=too-few-public-methods

    @staticmethod
    def add_to_characteristic(
        characteristic,
        uuid,
        *,
        read_perm=Attribute.OPEN,
        write_perm=Attribute.OPEN,
        max_length=20,
        fixed_length=False,
        initial_value=b""
    ):
        """Create a new Descriptor object, and add it to this Characteristic."""


class CharacteristicBuffer:  # pylint: disable=too-few-public-methods
    """Accumulates a Characteristic's incoming values in a FIFO buffer."""


class PacketBuffer:  # pylint: disable=too-few-public-methods
    """Accumulates a Characteristic's incoming packets in a FIFO buffer and facilitates packet aware
       outgoing writes. A packet's size is either the characteristic length or the maximum
       transmission unit (MTU), whichever is smaller. The MTU can change so check ``packet_size``
       before creating a buffer to store data.

       When we're the server, we ignore all connections besides the first to subscribe to
       notifications."""


class Characteristic:
    """Stores information about a BLE service characteristic and allows reading and writing of the
       characteristic's value."""

    # pylint: disable=too-few-public-methods

    BROADCAST = 0
    READ = 0
    WRITE = 0
    NOTIFY = 0
    INDICATE = 0
    WRITE_NO_RESPONSE = 0

    @staticmethod
    def add_to_service(
        service,
        uuid,
        *,
        properties=0,
        read_perm=Attribute.OPEN,
        write_perm=Attribute.OPEN,
        max_length=20,
        fixed_length=False,
        initial_value=None
    ):
        """Create a new Characteristic object, and add it to this Service."""
        raise NotImplementedError()


async def _get_mac():
    loop = asyncio.get_event_loop()
    reactor = AsyncioSelectorReactor(loop)
    bus = await client.connect(reactor, "system").asFuture(loop)
    objs = await utils.get_managed_objects(bus, loop, object_path_filter=None)
    bus.disconnect()
    for obj in objs.values():
        if "org.bluez.Adapter1" in obj:
            return obj["org.bluez.Adapter1"]["Address"]
    return None


_address = b"\x00\x00\x00\x00\x00\x00"  # pylint: disable=invalid-name
if utils:
    # pylint: disable=invalid-name
    _address = asyncio.get_event_loop().run_until_complete(_get_mac())

if _address:
    adapter = Adapter(_address)  # pylint: disable=invalid-name
