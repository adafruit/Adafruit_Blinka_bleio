# SPDX-FileCopyrightText: Copyright (c) 2020 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`_bleio.common`
=======================================================================

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""
from __future__ import annotations
from typing import Callable, Iterable, List, Optional, Tuple, Set, Union

import asyncio
import atexit
import platform
import threading
import time

from bleak import BleakClient, BleakScanner  # type: ignore[import]
from bleak.backends.characteristic import (  # type: ignore[import]
    BleakGATTCharacteristic,
    GattCharacteristicsFlags,
)
from bleak.backends.device import BLEDevice  # type: ignore[import]
from bleak.backends.scanner import AdvertisementData  # type: ignore[import]
from bleak.backends.service import BleakGATTService  # type: ignore[import]


from _bleio.address import Address
from _bleio.attribute import Attribute
from _bleio.exceptions import BluetoothError
from _bleio.scan_entry import ScanEntry
from _bleio.uuid_ import UUID

if platform.system() == "Linux":
    import re
    import signal
    import subprocess

Buf = Union[bytes, bytearray, memoryview]

# Singleton _bleio.adapter is defined after class Adapter.
adapter = None  # pylint: disable=invalid-name


class Adapter:  # pylint: disable=too-many-instance-attributes
    """Singleton _bleio.adapter is defined after class Adapter."""

    # Do blocking scans in chunks of this interval.
    _SCAN_INTERVAL = 0.25

    def __init__(self):
        if adapter:
            raise RuntimeError("Use the singleton _bleio.adapter")
        self._name = platform.node()
        # Unbounded FIFO for scan results
        self._scanning_in_progress = False
        # Created on demand in self._bleak_thread context.
        self._scanner = None
        self._connections = []
        self._bleak_loop = None
        self._bleak_thread = threading.Thread(target=self._run_bleak_loop)
        # Discard thread quietly on exit.
        self._bleak_thread.daemon = True
        self._bleak_thread_ready = threading.Event()
        self._bleak_thread.start()
        # Wait for thread to start.
        self._bleak_thread_ready.wait()

        # Not known yet.
        self._hcitool_is_usable = None
        self._hcitool = None
        self._hcidump = None
        self.ble_backend = None

        # Keep a cache of recently scanned devices, to avoid doing double
        # device scanning.
        self._cached_devices = {}

        # Clean up connections, etc. when exiting (even by KeyboardInterrupt)
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        """Clean up connections, so that the underlying OS software does not
        leave them open.
        """
        # Use a copy of the list because each connection will be deleted
        # on disconnect().
        for connection in self._connections.copy():
            connection.disconnect()

    @property
    def _use_hcitool(self) -> bool:
        """Determines whether to use the hcitool backend or default bleak, based on whether
        we want to and can use hcitool.
        """
        if self._hcitool_is_usable is None:
            self._hcitool_is_usable = False
            if platform.system() == "Linux":
                # Try a no-op HCI command; this will require privileges,
                # so we can see whether we can use hcitool in general.
                try:
                    subprocess.run(
                        ["hcitool", "cmd", "0x0", "0x0000"],
                        timeout=2.0,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    # Succeeded.
                    self._hcitool_is_usable = True
                except (subprocess.SubprocessError, FileNotFoundError, PermissionError):
                    # Lots of things can go wrong:
                    # no hcitool, no privileges (causes non-zero return code), too slow, etc.
                    pass
            if self.ble_backend:
                if self.ble_backend == "bleak":
                    # User requests bleak, so ignore hcitool.
                    self._hcitool_is_usable = False
                elif self.ble_backend == "hcitool":
                    if not self._hcitool_is_usable:
                        # User wants hcitool, but it's not working. Raise an exception.
                        raise EnvironmentError(
                            "ble_backend set to 'hcitool', but hcitool is unavailable"
                        )
                else:
                    raise ValueError(
                        "ble_backend setting not recognized. Should be 'hcitool' or 'bleak'."
                    )

        return self._hcitool_is_usable

    def _run_bleak_loop(self) -> None:
        self._bleak_loop = asyncio.new_event_loop()
        # Event loop is now available.
        self._bleak_thread_ready.set()
        self._bleak_loop.run_forever()

    def await_bleak(self, coro, timeout: Optional[float] = None):
        """Call an async routine in the bleak thread from sync code, and await its result."""
        # This is a concurrent.Future.
        future = asyncio.run_coroutine_threadsafe(coro, self._bleak_loop)
        return future.result(timeout)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def address(self) -> Optional[Address]:
        if platform.system() == "Linux":
            try:
                lines = subprocess.run(
                    ["bluetoothctl", "list"],
                    timeout=2.0,
                    check=True,
                    capture_output=True,
                ).stdout
            except subprocess.SubprocessError:
                return None
            for line in lines.decode("utf-8").splitlines():
                match = re.search(r"(..:..:..:..:..:..).*\[default\]", line)
                if match:
                    return Address(string=match.group(1))

        # Linux method failed, or not on Linux.
        return None

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    # pylint: disable=too-many-arguments
    def start_advertising(
        self,
        data: Buf,
        *,
        scan_response: Optional[Buf] = None,
        connectable: bool = True,
        anonymous: bool = False,
        timeout: int = 0,
        interval: float = 0.1,
    ) -> None:
        raise NotImplementedError("Advertising not implemented")

    def stop_advertising(self) -> None:
        """Stop sending advertising packets."""
        raise NotImplementedError("Advertising not implemented")

    # pylint: disable=too-many-arguments
    def start_scan(
        self,
        prefixes: Buf = b"",
        *,
        buffer_size: int = 512,  # pylint: disable=unused-argument
        extended: bool = False,  # pylint: disable=unused-argument
        timeout: Optional[float] = None,
        interval: float = 0.1,  # pylint: disable=unused-argument
        window: float = 0.1,  # pylint: disable=unused-argument
        minimum_rssi: int = -80,
        active: bool = True,  # pylint: disable=unused-argument
    ) -> Iterable[ScanEntry]:
        """
        Starts a BLE scan and returns an iterator of results. Advertisements and scan responses are
        filtered and returned separately.

        :param sequence prefixes: Sequence of byte string prefixes to filter advertising packets
            with. A packet without an advertising structure that matches one of the prefixes is
            ignored. Format is one byte for length (n) and n bytes of prefix and can be repeated.
        :param int buffer_size: the maximum number of advertising bytes to buffer.
        :param bool extended: When True, support extended advertising packets.
           Increasing buffer_size is recommended when this is set.
        :param float timeout: the scan timeout in seconds.
          If None, will scan until `stop_scan` is called.
        :param float interval: the interval (in seconds) between the start
           of two consecutive scan windows.  Must be in the range 0.0025 - 40.959375 seconds.
        :param float window: the duration (in seconds) to scan a single BLE channel.
           window must be <= interval.
        :param int minimum_rssi: the minimum rssi of entries to return.
        :param bool active: retrieve scan responses for scannable advertisements.
        :returns: an iterable of ``ScanEntry`` objects
        :rtype: iterable"""

        # Remember only the most recently advertised devices.
        # In the future, we might remember these for a few minutes.
        self._clear_device_cache()

        if self._use_hcitool:
            yield from self._start_scan_hcitool(
                prefixes,
                timeout=timeout,
                minimum_rssi=minimum_rssi,
                active=active,
            )
            return

        self._scanning_in_progress = True

        start = time.time()
        while self._scanning_in_progress and (
            timeout is None or time.time() - start < timeout
        ):
            for device, advertisement_data in self.await_bleak(
                self._scan_for_interval(self._SCAN_INTERVAL)
            ):
                if advertisement_data.rssi < minimum_rssi:
                    continue
                self._cache_device(device)
                scan_entry = ScanEntry._from_bleak(  # pylint: disable=protected-access
                    device, advertisement_data
                )
                if not scan_entry.matches(prefixes, match_all=False):
                    continue
                yield scan_entry

    @staticmethod
    def _parse_hcidump_data(
        buffered: List[bytes], prefixes: bytes, minimum_rssi: int, active: bool
    ):
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

                scan_entry = ScanEntry(
                    address=address,
                    rssi=rssi,
                    advertisement_bytes=data,
                    connectable=event_type < 0x2,
                    scan_response=event_type == 0x4,
                )
                if scan_entry.matches(prefixes, match_all=False):
                    return scan_entry
        return None

    def _start_scan_hcitool(
        self,
        prefixes: Buf,
        *,
        timeout: Optional[float],
        minimum_rssi: int,
        active: bool,
    ) -> Iterable:
        """hcitool scanning (only on Linux)"""
        # hcidump outputs the full advertisement data, assuming it's run privileged.
        # Since hcitool is privileged, we assume hcidump is too.
        # pylint: disable=consider-using-with
        self._hcidump = subprocess.Popen(
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
        # pylint: enable=consider-using-with
        # Throw away the first two output lines of hcidump because they are version info.
        self._hcidump.stdout.readline()  # type: ignore[union-attr]
        self._hcidump.stdout.readline()  # type: ignore[union-attr]
        returncode = self._hcidump.poll()
        start_time = time.monotonic()
        buffered: List[bytes] = []
        while returncode is None and (
            timeout is None or time.monotonic() - start_time < timeout
        ):
            line = self._hcidump.stdout.readline()  # type: ignore[union-attr]
            # print(line, line[0])
            if line[0] != 32:  # 32 is ascii for space
                if buffered:
                    parsed = self._parse_hcidump_data(
                        buffered, prefixes, minimum_rssi, active
                    )
                    if parsed:
                        yield parsed
                    buffered.clear()
            buffered.append(line)
            returncode = self._hcidump.poll()
        self.stop_scan()

    async def _scan_for_interval(
        self, interval: float
    ) -> Tuple[BLEDevice, AdvertisementData]:
        """Scan advertisements for the given interval and tuples (device, advertisement_data)
        for all advertisements heard.
        """
        if not self._scanner:
            self._scanner = BleakScanner(loop=self._bleak_loop)

        await self._scanner.start()
        await asyncio.sleep(interval)
        await self._scanner.stop()
        return self._scanner.discovered_devices_and_advertisement_data.values()

    def stop_scan(self) -> None:
        """Stop scanning before timeout may have occurred."""
        if self._use_hcitool:
            if self._hcitool:
                if self._hcitool.poll() is None:
                    self._hcitool.send_signal(signal.SIGINT)
                    self._hcitool.wait()
                self._hcitool = None
            if self._hcidump:
                if self._hcidump.poll() is None:
                    self._hcidump.send_signal(signal.SIGINT)
                    self._hcidump.wait()
                self._hcidump = None
        self._scanning_in_progress = False
        self._scanner = None

    @property
    def connected(self) -> bool:
        return bool(self._connections)

    @property
    def connections(self) -> Iterable[Connection]:
        return tuple(self._connections)

    def connect(self, address: Address, *, timeout: float) -> None:
        return self.await_bleak(self._connect_async(address, timeout=timeout))

    # pylint: disable=protected-access
    async def _connect_async(self, address: Address, *, timeout: float) -> Connection:
        device = self._cached_device(address)
        # Use cached device if possible, to avoid having BleakClient do
        # a scan again.
        client = BleakClient(device if device else address._bleak_address)
        # connect() takes a timeout, but it's a timeout to do a
        # discover() scan, not an actual connect timeout.
        try:
            await client.connect(timeout=timeout)
            # This does not seem to connect reliably.
            # await asyncio.wait_for(client.connect(), timeout)
        except asyncio.TimeoutError:
            raise BluetoothError("Failed to connect: timeout") from asyncio.TimeoutError

        connection = Connection._from_bleak(address, client)
        self._connections.append(connection)
        return connection

    def delete_connection(self, connection: Connection) -> None:
        """Remove the specified connection of the list of connections held by the adapter.
        (Blinka _bleio only).
        """
        self._connections.remove(connection)

    def erase_bonding(self) -> None:
        raise NotImplementedError(
            "Use the host computer's BLE comamnds to reset bonding information"
        )

    def _cached_device(self, address: Address) -> Optional[BLEDevice]:
        """Return a device recently found during scanning with the given address."""
        return self._cached_devices.get(address)

    def _clear_device_cache(self) -> None:
        self._cached_devices.clear()

    def _cache_device(self, device: BLEDevice) -> None:
        self._cached_devices[device.address] = device


# Create adapter singleton.
adapter = Adapter()
adapter.enabled = True


# pylint: disable=too-many-instance-attributes
class Characteristic:
    """Stores information about a BLE service characteristic and allows reading
    and writing of the characteristic's value."""

    BROADCAST = 0x1
    """property: allowed in advertising packets"""
    INDICATE = 0x2
    """property: server will indicate to the client when the value is set and wait for a response"""
    NOTIFY = 0x4
    """property: server will notify the client when the value is set"""
    READ = 0x8
    """property: clients may read this characteristic"""
    WRITE = 0x10
    """property: clients may write this characteristic; a response will be sent back"""
    WRITE_NO_RESPONSE = 0x20
    """property: clients may write this characteristic; no response will be sent back"""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        uuid: UUID,
        properties: int = 0,
        read_perm: int = Attribute.OPEN,
        write_perm: int = Attribute.OPEN,
        max_length: int = 20,
        fixed_length: bool = False,
        initial_value: Optional[Buf] = None,
    ):
        """There is no regular constructor for a Characteristic.  A
        new local Characteristic can be created and attached to a
        Service by calling `add_to_service()`.  Remote Characteristic
        objects are created by `_bleio.Connection.discover_remote_services`
        as part of remote Services."""
        self._uuid = uuid
        self._properties = properties
        self._read_perm = read_perm
        self._write_perm = write_perm
        self._max_length = max_length
        self._fixed_length = fixed_length
        self._initial_value = initial_value
        self._service: Optional[Service] = None
        self._descriptors: Tuple["Descriptor"] = ()  # type: ignore[name-defined,assignment]
        self._bleak_gatt_characteristic = None
        self._notify_callbacks: Set[Callable[[Buf], None]] = set()

    @classmethod
    def add_to_service(
        cls,
        service: "Service",
        uuid: UUID,
        *,
        properties: int = 0,
        read_perm: int = Attribute.OPEN,
        write_perm: int = Attribute.OPEN,
        max_length: int = 20,
        fixed_length: bool = False,
        initial_value: Optional[Buf] = None,
    ) -> "Characteristic":
        """Create a new Characteristic object, and add it to this Service.

        :param Service service: The service that will provide this characteristic
        :param UUID uuid: The uuid of the characteristic
        :param int properties: The properties of the characteristic,
           specified as a bitmask of these values bitwise-or'd together:
           `BROADCAST`, `INDICATE`, `NOTIFY`, `READ`, `WRITE`, `WRITE_NO_RESPONSE`.
        :param int read_perm: Specifies whether the characteristic can be read by a client,
           and if so, which security mode is required.
           Must be one of the integer values `_bleio.Attribute.NO_ACCESS`, `_bleio.Attribute.OPEN`,
           `_bleio.Attribute.ENCRYPT_NO_MITM`, `_bleio.Attribute.ENCRYPT_WITH_MITM`,
           `_bleio.Attribute.LESC_ENCRYPT_WITH_MITM`,
           `_bleio.Attribute.SIGNED_NO_MITM`, or `_bleio.Attribute.SIGNED_WITH_MITM`.
        :param int write_perm: Specifies whether the characteristic can be written by a client,
           and if so, which security mode is required.
           Values allowed are the same as ``read_perm``.
        :param int max_length: Maximum length in bytes of the characteristic value.
           The maximum allowed is is 512, or possibly 510 if ``fixed_length`` is False.
           The default, 20, is the maximum number of data bytes
           that fit in a single BLE 4.x ATT packet.
        :param bool fixed_length: True if the characteristic value is of fixed length.
        :param buf initial_value: The initial value for this characteristic.
           If not given, will be filled with zeros.

        :return: the new Characteristic."""
        charac = Characteristic(
            uuid=uuid,
            properties=properties,
            read_perm=read_perm,
            write_perm=write_perm,
            max_length=max_length,
            fixed_length=fixed_length,
            initial_value=initial_value,
        )
        charac._service = service  # pylint: disable=protected-access
        return charac

    @classmethod
    def _from_bleak(
        cls, service: "Service", _bleak_characteristic: BleakGATTCharacteristic
    ) -> "Characteristic":
        properties = 0
        for prop in _bleak_characteristic.properties:
            properties |= GattCharacteristicsFlags[prop.replace("-", "_")].value
        charac = Characteristic.add_to_service(
            service=service,
            uuid=UUID(_bleak_characteristic.uuid),
            properties=properties,
            read_perm=Attribute.OPEN,
            write_perm=Attribute.OPEN,
        )

        # pylint: disable=protected-access
        charac._bleak_gatt_characteristic = _bleak_characteristic
        # pylint: enable=protected-access
        return charac

    def _bleak_characteristic(self) -> BleakGATTCharacteristic:
        """BleakGATTCharacteristic object"""
        return self._bleak_gatt_characteristic

    @property
    def properties(self) -> int:
        """An int bitmask representing which properties are set, specified as bitwise or'ing of
        of these possible values.
        `BROADCAST`, `INDICATE`, `NOTIFY`, `READ`, `WRITE`, `WRITE_NO_RESPONSE`.
        """
        return self._properties

    @property
    def uuid(self) -> UUID:
        """The UUID of this characteristic. (read-only)
        Will be ``None`` if the 128-bit UUID for this characteristic is not known."""
        return self._uuid

    @property
    def value(self) -> Union[bytes, None]:
        """The value of this characteristic."""
        return adapter.await_bleak(
            # pylint: disable=protected-access
            self.service.connection._bleak_client.read_gatt_char(self.uuid._bleak_uuid)
        )

    @value.setter
    def value(self, val) -> None:
        adapter.await_bleak(
            # BlueZ DBus cannot take a bytes here, though it can take a tuple, etc.
            # So use a bytearray.
            # pylint: disable=protected-access
            self.service.connection._bleak_client.write_gatt_char(
                self.uuid._bleak_uuid,
                bytearray(val),
                response=self.properties & Characteristic.WRITE,
            )
        )

    @property
    def descriptors(self) -> Tuple["Descriptor"]:  # type: ignore[name-defined]
        """A tuple of :py:class:~`Descriptor` that describe this characteristic. (read-only)"""
        return self._descriptors

    @property
    def service(self) -> "Service":
        """The Service this Characteristic is a part of."""
        if self._service is None:
            raise ValueError("Characteristic not added to a Service")
        return self._service

    def set_cccd(self, *, notify: bool = False, indicate: bool = False) -> None:
        """Set the remote characteristic's CCCD to enable or disable notification and indication.

        :param bool notify: True if Characteristic should receive notifications of remote writes
        :param float indicate: True if Characteristic should receive indications of remote writes
        """
        if indicate:
            raise NotImplementedError("Indicate not available")

        # pylint: disable=protected-access
        if notify:
            adapter.await_bleak(
                self.service.connection._bleak_client.start_notify(
                    self._bleak_gatt_characteristic.uuid,
                    self._notify_callback,
                )
            )
        else:
            adapter.await_bleak(
                self._service.connection._bleak_client.stop_notify(
                    self._bleak_gatt_characteristic.uuid
                )
            )

    def _add_notify_callback(self, callback: Callable[[Buf], None]):
        """Add a callback to call when a notify happens on this characteristic."""
        self._notify_callbacks.add(callback)

    def _remove_notify_callback(self, callback: Callable[[Buf], None]):
        """Remove a callback to call when a notify happens on this characteristic."""
        self._notify_callbacks.remove(callback)

    # pylint: disable=unused-argument
    def _notify_callback(self, handle: Optional[int], data: Buf):
        # pylint: disable=protected-access
        # Note: Right now we can't vet the handle, because it may be None.
        for callback in self._notify_callbacks:
            callback(data)

    def __repr__(self) -> str:
        if self.uuid:
            return f"<Characteristic: {self.uuid}>"
        return "<Characteristic: uuid is None>"


class Connection:
    """A BLE connection to another device. Used to discover and interact with services on the other
    device.

    Usage::

       import _bleio

       my_entry = None
       for entry in _bleio.adapter.scan(2.5):
           if entry.name is not None and entry.name == 'InterestingPeripheral':
               my_entry = entry
               break

       if not my_entry:
           raise Exception("'InterestingPeripheral' not found")

       connection = _bleio.adapter.connect(my_entry.address, timeout=10)"""

    def __init__(self, address: Address):
        """Connections should not be created directly.
        Instead, to initiate a connection use `_bleio.Adapter.connect`.
        Connections may also be made when another device initiates a connection. To use a Connection
        created by a peer, read the `_bleio.Adapter.connections` property.

        :param Address address: Address of device to connect to
        """
        self._address = address
        self.__bleak_client = None

    @classmethod
    def _from_bleak(cls, address: Address, _bleak_client: BleakClient) -> "Connection":
        """Create a Connection from bleak information.

        :param Address address: Address of device to connect to
        :param BleakClient _bleak_client: BleakClient used to make connection. (Blinka _bleio only)
        """
        conn = Connection(address)
        conn.__bleak_client = (  # pylint: disable=protected-access,unused-private-member
            _bleak_client
        )
        return conn

    @property
    def _bleak_client(self):
        return self.__bleak_client

    def disconnect(self) -> None:
        """Disconnects from the remote peripheral. Does nothing if already disconnected."""
        adapter.delete_connection(self)
        adapter.await_bleak(self._disconnect_async())

    async def _disconnect_async(self) -> None:
        """Disconnects from the remote peripheral. Does nothing if already disconnected."""
        await self.__bleak_client.disconnect()

    def pair(self, *, bond: bool = True) -> None:
        """Pair to the peer to improve security."""
        raise NotImplementedError("Pairing not implemented")

    def discover_remote_services(
        self, service_uuids_whitelist: Optional[Iterable] = None
    ) -> Tuple[Service]:
        return adapter.await_bleak(
            self._discover_remote_services_async(service_uuids_whitelist)
        )

    async def _discover_remote_services_async(
        self, service_uuids_whitelist: Optional[Iterable] = None
    ) -> Tuple[Service]:
        """Do BLE discovery for all services or for the given service UUIDS,
         to find their handles and characteristics, and return the discovered services.
         `Connection.connected` must be True.

        :param iterable service_uuids_whitelist:

          an iterable of :py:class:~`UUID` objects for the services provided by the peripheral
          that you want to use.

          The peripheral may provide more services, but services not listed are ignored
          and will not be returned.

          If service_uuids_whitelist is None, then all services will undergo discovery, which can be
          slow.

          If the service UUID is 128-bit, or its characteristic UUID's are 128-bit, you
          you must have already created a :py:class:~`UUID` object for that UUID in order for the
          service or characteristic to be discovered. Creating the UUID causes the UUID to be
          registered for use. (This restriction may be lifted in the future.)

        :return: A tuple of `Service` objects provided by the remote peripheral.
        """

        # Fetch the services.
        bleak_services = self.__bleak_client.services

        # pylint: disable=protected-access
        if service_uuids_whitelist:
            filtered_bleak_services = tuple(
                s for s in bleak_services if UUID(s.uuid) in service_uuids_whitelist
            )
        else:
            filtered_bleak_services = bleak_services

        return tuple(
            Service._from_bleak(self, bleak_service)
            for bleak_service in filtered_bleak_services
        )

    @property
    def connected(self) -> bool:
        """True if connected to the remote peer."""
        return self.__bleak_client.is_connected

    @property
    def paired(self) -> bool:
        """True if paired to the remote peer."""
        raise NotImplementedError("Pairing not implemented")

    @property
    def connection_interval(self) -> float:
        """Time between transmissions in milliseconds. Will be multiple of 1.25ms. Lower numbers
        increase speed and decrease latency but increase power consumption.

        When setting connection_interval, the peer may reject the new interval and
        `connection_interval` will then remain the same.

        Apple has additional guidelines that dictate should be a multiple of 15ms except if HID is
        available. When HID is available Apple devices may accept 11.25ms intervals."""
        raise NotImplementedError()

    @connection_interval.setter
    def connection_interval(self, value: float) -> None:
        raise NotImplementedError()

    @property
    def max_packet_length(self) -> int:
        """The maximum number of data bytes that can be sent in a single transmission,
        not including overhead bytes.

        This is the maximum number of bytes that can be sent in a notification,
        which must be sent in a single packet.
        But for a regular characteristic read or write, may be sent in multiple packets,
        so this limit does not apply."""
        raise NotImplementedError("max_packet_length not available")

    def __repr__(self):
        return f"<Connection: {self._address}"


class Service:
    """Stores information about a BLE service and its characteristics."""

    def __init__(
        self,
        uuid: UUID,
        *,
        secondary: bool = False,
        remote: bool = False,
    ):
        """Create a new Service identified by the specified UUID. It can be accessed by all
        connections. This is known as a Service server. Client Service objects are created via
        `_bleio.Connection.discover_remote_services`.

        To mark the Service as secondary, pass `True` as :py:data:`secondary`.

        :param UUID uuid: The uuid of the service
        :param bool secondary: If the service is a secondary one

        :return: the new Service
        """
        self._uuid = uuid
        self._secondary = secondary
        self._remote = remote
        self._connection = None
        self._characteristics = ()
        self._bleak_gatt_service = None

    # pylint: disable=protected-access
    @classmethod
    def _from_bleak(
        cls,
        connection: Connection,
        bleak_gatt_service: BleakGATTService,
    ) -> Service:
        service = cls(UUID(bleak_gatt_service.uuid), remote=True)
        service._connection = connection
        service._characteristics = tuple(
            Characteristic._from_bleak(service, bleak_characteristic)
            for bleak_characteristic in bleak_gatt_service.characteristics
        )
        service._bleak_gatt_service = bleak_gatt_service
        return service

    @property
    def _bleak_service(self):
        """BleakGATTService object"""
        return self._bleak_gatt_service

    @property
    def characteristics(self) -> Tuple[Characteristic]:
        """A tuple of :py:class:`Characteristic` designating the characteristics that are offered by
        this service. (read-only)"""
        return self._characteristics

    @property
    def remote(self) -> bool:
        """True if this is a service provided by a remote device. (read-only)"""
        return self._remote

    @property
    def secondary(self) -> bool:
        """True if this is a secondary service. (read-only)"""
        return self._secondary

    @property
    def uuid(self) -> Union[UUID, None]:
        """The UUID of this service. (read-only)
        Will be ``None`` if the 128-bit UUID for this service is not known.
        """
        return self._uuid

    @property
    def connection(self) -> Connection:
        """Connection associated with this service, if any."""
        return self._connection

    def __repr__(self) -> str:
        if self.uuid:
            return f"<Service: {self.uuid}>"
        return "<Service: uuid is None>"
