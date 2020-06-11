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

Buf = Union[bytes, bytearray, memoryview]

# Singleton _bleio.adapter is defined at the ned of this file.
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
        # bleak has no API for the address yet.
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
                scan_entry = ScanEntry(device)
                if not scan_entry.matches(prefixes, all=False):
                    continue
                yield scan_entry

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
        self._scanning_in_progress = False

    @property
    def connected(self):
        return bool(self._connections)

    @property
    def connections(self) -> Iterable[Connection]:
        return tuple(self._connections)

    def connect(self, address: Address, *, timeout: float) -> None:
        return self.await_bleak(self._connect_async(address, timeout=timeout))

    async def _connect_async(self, address: Address, *, timeout: float) -> None:
        client = BleakClient(address.bleak_address)
        # connect() takes a timeout, but it's a timeout to do a
        # discover() scan, not an actual connect timeout.
        # TODO: avoid the second discovery.
        try:
            await client.connect(timeout=timeout)
            # This does not seem to connect reliably.
            # await asyncio.wait_for(client.connect(), timeout)
        except asyncio.TimeoutError:
            raise BluetoothError("Failed to connect: timeout")

        connection = Connection.from_bleak(address, client)
        self._connections.append(connection)
        return connection

    def delete_connection(self, connection: Connection) -> None:
        """Remove the specified connection of the list of connections held by the adapter.
        (Blinka _bleio only).
        """
        self._connections.remove(connection)

    def erase_bonding(self) -> None:
        raise NotImplementedError(
            "Use the host computer's BLE comamnds to reset bonding infomration"
        )


# Create adapter singleton.
adapter = Adapter()
adapter.enabled = True
