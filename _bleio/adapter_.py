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

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""

from typing import Any, Iterable, Union

import asyncio
import os
from threading import Thread
import time

# janus.Queue is thread-safe and can be used from both sync and async code.
import janus
from bleak import BleakClient, BleakScanner

import _bleio


class Adapter:
    def __init__(self):
        if _bleio.adapter:
            raise RuntimeError("Use the singleton _bleio.adapter")
        self._name = os.uname().nodename
        # Unbounded FIFO for scan results
        self._scan_queue = None
        self._scan_thread = None
        self._scanning_in_progress = False
        self._connections = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def address(self) -> _bleio.Address:
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
        data: Union[bytes, bytearray],
        *,
        scan_response: Union[bytes, bytearray] = None,
        connectable: bool = True,
        interval: float = 0.1
    ) -> None:
        raise NotImplementedError("Advertising not implemented")

    def stop_advertising(self) -> None:
        """Stop sending advertising packets."""
        raise NotImplementedError("Advertising not implemented")

    def start_scan(
        self,
        prefixes: Union[bytes, bytearray] = b"",
        *,
        buffer_size: int = 512,
        extended: bool = False,
        timeout: float = None,
        interval: float = 0.1,
        window: float = 0.1,
        minimum_rssi: int = -80,
        active: bool = True
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

        self._scanning_in_progress = True

        # Run the scanner in a separate thread
        self._scan_thread = Thread(target=self._start_scan_async, args=(timeout,))
        self._scan_thread.start()

        # Wait for queue creation, which must be done
        # in the async thread so it gets the right event loop.
        while not self._scan_queue:
            pass

        while True:
            scan_entry = self._next_from_queue()
            if scan_entry is None:
                # Finish iterator when sentinel end value is received.
                return
            if scan_entry.rssi < minimum_rssi:
                continue
            yield scan_entry

    def stop_scan(self) -> None:
        self._scanning_in_progress = False
        # Drain the queue of any unread entries.
        # The last entry will be a None.
        while self._next_from_queue() is not None:
            pass

    def _next_from_queue(self) -> Any:
        """Read next item from scan entry queue. When done, clean up and return None."""
        queue = self._scan_queue
        scan_entry = queue.sync_q.get()
        # Tell producer we read the entry. This allows clean shutdown when done.
        queue.sync_q.task_done()

        # When sentinel end value is received,
        # Wait for async thread to finish, and then discard queue.
        if scan_entry is None:
            self._scan_thread.join()
            self._scan_queue = None

        return scan_entry

    def _start_scan_async(self, timeout):
        """Run the async part of start_scan()."""
        # Creates event loop and cleans it up when done.
        asyncio.run(self._scan(timeout), debug=True)
        self._scanning_in_progress = False

    async def _scan(self, timeout: Union[float, None]) -> None:
        """
        Run as a task to scan and add ScanEntry objects to the queue.
        Repeat until timeout period has elapsed, or if timeout is None,
        until stop_scan is called()
        """
        queue = self._scan_queue = janus.Queue()

        # If timeout is forever, do it in chunks.

        # The bleak discover(timeout) is the total time to spend scanning.
        # No intermediate results are returned during the timeout period,
        # unlike _bleio.start_scan(). So scan in short increments to emulate
        # returning intermediate results.

        # Some bleak backends provide a callback for each scan result,
        # but corebluetooth (MacOS) does not, as of this writing,
        # so we can't use the callback mechanism to add to the queue
        # when received.

        start = time.time()
        bleak_timeout = min(timeout, 0.25)

        while self._scanning_in_progress:
            async with BleakScanner() as scanner:
                await asyncio.sleep(bleak_timeout)
                devices = await scanner.get_discovered_devices()
            for device in devices:
                # Convert bleak scan result to a ScanEntry and save it.
                if device is not None:
                    # TODO: filter results
                    await queue.async_q.put(_bleio.ScanEntry(device))
            if timeout is not None and time.time() - start > timeout:
                # Quit when timeout period has elapsed.
                break

        # Finished scanning.
        # Put sentinel end iteration value on queue.
        await queue.async_q.put(None)

        # Wait for queue to be emptied.
        await queue.async_q.join()
        queue.close()
        await queue.wait_closed()

    @property
    def connected(self):
        return bool(self._connections)

    @property
    def connections(self) -> Iterable:
        return tuple(self._connections)

    def connect(self, address: _bleio.Address, *, timeout: float) -> None:
        return _bleio.call_async(self._connect_async(address, timeout=timeout))

    async def _connect_async(self, address: _bleio.Address, *, timeout: float) -> None:
        client = BleakClient(address)
        try:
            asyncio.wait_for(client.connect(), timeout)
        except asyncio.TimeoutError:
            raise _bleio.BluetoothError("Failed to connect: timeout")

        self._connections.append(_bleio.Connection.from_bleak_client(address, client))

    def delete_connection(self, connection: _bleio.Connection) -> None:
        """Remove the specified connection of the list of connections held by the adapter.
        (Blinka _bleio only).
        """
        self._connections.remove(connection)

    def erase_bonding(self) -> None:
        raise NotImplementedError(
            "Use the host computer's BLE comamnds to reset bonding infomration"
        )
