# The MIT License (MIT)
#
# Copyright (c) 2020 Dan Halbert for Adafruit Industries LLC
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
`_bleio.adapter_`
=======================================================================

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""
from __future__ import annotations
from typing import Iterable, Union

import asyncio
import platform
import threading
import time

from bleak import BleakClient, BleakScanner

from _bleio.address import Address
from _bleio.connection import Connection
from _bleio.exceptions import BluetoothError
from _bleio.scan_entry import ScanEntry

if platform.system() == "Linux":
    import re
    import signal
    import subprocess

Buf = Union[bytes, bytearray, memoryview]

# Singleton _bleio.adapter is defined at the end of this file.
adapter = None  # pylint: disable=invalid-name


class Adapter:
    # Do blocking scans in chunks of this interval.
    _SCAN_INTERVAL = 0.25

    def __init__(self):
        if adapter:
            raise RuntimeError("Use the singleton _bleio.adapter")
        self._name = platform.node()
        # Unbounded FIFO for scan results
        self._scanning_in_progress = False
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

    @property
    def _use_hcitool(self):
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
                except subprocess.SubprocessError:
                    # Lots of things can go wrong:
                    # no hcitool, no privileges (causes non-zero return code), too slow, etc.
                    pass

        return self._hcitool_is_usable

    def _run_bleak_loop(self):
        self._bleak_loop = asyncio.new_event_loop()
        # Event loop is now available.
        self._bleak_thread_ready.set()
        self._bleak_loop.run_forever()

    def await_bleak(self, coro, timeout=None):
        """Call an async routine in the bleak thread from sync code, and await its result."""
        # This is a concurrent.Future.
        future = asyncio.run_coroutine_threadsafe(coro, self._bleak_loop)
        return future.result(timeout)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def address(self) -> Address:
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
    def name(self, value: str):
        self._name = value

    def start_advertising(
        self,
        data: Buf,
        *,
        scan_response: Buf = None,
        connectable: bool = True,
        interval: float = 0.1
    ) -> None:
        raise NotImplementedError("Advertising not implemented")

    def stop_advertising(self) -> None:
        """Stop sending advertising packets."""
        raise NotImplementedError("Advertising not implemented")

    def start_scan(
        self,
        prefixes: Buf = b"",
        *,
        buffer_size: int = 512,  # pylint: disable=unused-argument
        extended: bool = False,  # pylint: disable=unused-argument
        timeout: float = None,
        interval: float = 0.1,  # pylint: disable=unused-argument
        window: float = 0.1,  # pylint: disable=unused-argument
        minimum_rssi: int = -80,
        active: bool = True  # pylint: disable=unused-argument
    ) -> Iterable:
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
        :returns: an iterable of `_bleio.ScanEntry` objects
        :rtype: iterable"""

        if self._use_hcitool:
            for scan_entry in self._start_scan_hcitool(
                prefixes, timeout=timeout, minimum_rssi=minimum_rssi, active=active,
            ):
                yield scan_entry
            return

        scanner = BleakScanner(loop=self._bleak_loop)
        self._scanning_in_progress = True

        start = time.time()
        while self._scanning_in_progress and (
            timeout is None or time.time() - start < timeout
        ):
            for device in self.await_bleak(
                self._scan_for_interval(scanner, self._SCAN_INTERVAL)
            ):
                if not device or device.rssi < minimum_rssi:
                    continue
                scan_entry = ScanEntry._from_bleak(  # pylint: disable=protected-access
                    device
                )
                if not scan_entry.matches(prefixes, all=False):
                    continue
                yield scan_entry

    @staticmethod
    def _parse_hcidump_data(buffered, prefixes, minimum_rssi, active):
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
                if scan_entry.matches(prefixes, all=False):
                    return scan_entry
        return None

    def _start_scan_hcitool(
        self, prefixes: Buf, *, timeout: float, minimum_rssi, active: bool,
    ) -> Iterable:
        """hcitool scanning (only on Linux)"""
        # hcidump outputs the full advertisement data, assuming it's run privileged.
        # Since hcitool is privileged, we assume hcidump is too.
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
                    parsed = self._parse_hcidump_data(
                        buffered, prefixes, minimum_rssi, active
                    )
                    if parsed:
                        yield parsed
                    buffered.clear()
            buffered.append(line)
            returncode = self._hcitool.poll()
        self.stop_scan()

    async def _scan_for_interval(self, scanner, interval: float) -> Iterable[ScanEntry]:
        """Scan advertisements for the given interval and return ScanEntry objects
        for all advertisements heard.
        """
        await scanner.start()
        await asyncio.sleep(interval)
        await scanner.stop()
        return await scanner.get_discovered_devices()

    def stop_scan(self) -> None:
        """Stop scanning before timeout may have occurred."""
        if self._use_hcitool and self._hcitool:
            if self._hcitool.returncode is None:
                self._hcitool.send_signal(signal.SIGINT)
                self._hcitool.wait()
            self._hcitool = None
        self._scanning_in_progress = False

    @property
    def connected(self):
        return bool(self._connections)

    @property
    def connections(self) -> Iterable[Connection]:
        return tuple(self._connections)

    def connect(self, address: Address, *, timeout: float) -> None:
        return self.await_bleak(self._connect_async(address, timeout=timeout))

    # pylint: disable=protected-access
    async def _connect_async(self, address: Address, *, timeout: float) -> None:
        client = BleakClient(address._bleak_address)
        # connect() takes a timeout, but it's a timeout to do a
        # discover() scan, not an actual connect timeout.
        # TODO: avoid the second discovery.
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


# Create adapter singleton.
adapter = Adapter()
adapter.enabled = True
