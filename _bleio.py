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
import struct
import time

import bleak

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"


class Address:
    """Create a new Address object encapsulating the address value."""

    # pylint: disable=too-few-public-methods
    def __init__(self, address):
        if isinstance(address, bytes):
            self.address_bytes = address
        elif isinstance(address, str):
            address = address.split(":")
            self.address_bytes = bytes([int(x, 16) for x in address])


class ScanEntry:
    """Should not be instantiated directly. Use `_bleio.Adapter.start_scan`."""

    def __init__(self, bleak_device):
        self.rssi = bleak_device.rssi
        self._data_dict = {}
        if "manufacturer_data" in bleak_device.metadata:
            mfg_data = bleak_device.metadata["manufacturer_data"]
            self._data_dict[0xFF] = []
            for mfg in mfg_data:
                self._data_dict[0xFF].append(
                    struct.pack("<H", mfg) + bytes(mfg_data[mfg])
                )
        # print(self._data_dict)
        self.address = Address(bleak_device.address)

        self.advertisement_bytes = ScanEntry._encode_data(self._data_dict)
        # print(bleak_device.address, bleak_device.name, bleak_device.metadata)

        self.connectable = bool(bleak_device.metadata["uuids"])
        self.scan_response = False

    @staticmethod
    def _compute_length(data_dict, *, key_encoding="B"):
        """Computes the length of the encoded data dictionary."""
        value_size = 0
        for value in data_dict.values():
            if isinstance(value, list):
                for subv in value:
                    value_size += len(subv)
            else:
                value_size += len(value)
        return (
            len(data_dict) + len(data_dict) * struct.calcsize(key_encoding) + value_size
        )

    @staticmethod
    def _encode_data(data_dict, *, key_encoding="B"):
        """Helper which encodes dictionaries into length encoded structures with the given key
           encoding."""
        length = ScanEntry._compute_length(data_dict, key_encoding=key_encoding)
        data = bytearray(length)
        key_size = struct.calcsize(key_encoding)
        i = 0
        for key, value in data_dict.items():
            if isinstance(value, list):
                value = b"".join(value)
            item_length = key_size + len(value)
            struct.pack_into("B", data, i, item_length)
            struct.pack_into(key_encoding, data, i + 1, key)
            data[i + 1 + key_size : i + 1 + item_length] = bytes(value)
            i += 1 + item_length
        return data

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
                    print(
                        "matches", prefixes, self._data_dict, self.advertisement_bytes
                    )
                    return True
                if all and not found:
                    return False
            elif all:
                return False
            i += prefix_len
        if all:
            print("matches", prefixes, self._data_dict, self.advertisement_bytes)
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
        # pylint: disable=unused-argument
        # For now we ignore self, we may use it in the future though.
        # pylint: disable=no-self-use
        start_time = time.monotonic()
        while not timeout or time.monotonic() - start_time < timeout:
            devices = asyncio.get_event_loop().run_until_complete(
                bleak.discover(timeout=interval)
            )
            for device in devices:
                scan_entry = ScanEntry(device)
                if scan_entry.matches(prefixes, all=False):
                    yield scan_entry

    def stop_scan(self):
        """Stop the current scan."""
        # This does nothing for now because the scan isn't actually ongoing.


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


adapter = Adapter(b"\x00\x00\x00\x00\x00\x00")  # pylint: disable=invalid-name
