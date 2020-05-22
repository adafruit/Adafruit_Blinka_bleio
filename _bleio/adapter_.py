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

from typing import Iterable, Union

import asyncio
from threading import Thread
import time

# janus.Queue is thread-safe and can be used from both sync and async code.
import janus
from bleak import BleakScanner

import _bleio


class Adapter:
    def __init__(self):
        if _bleio.adapter:
            return _bleio.adapter
        self._name = "TODO"
        self._scan_results_queue = None
        # Unbounded FIFO for scan results
        self._scanning_in_progress = False

    @property
    def enabled(self) -> bool:
        pass  # TODO

    @enabled.setter
    def enabled(self, value: bool):
        pass  # TODO

    @property
    def address(self) -> _bleio.Address:
        self.enabled = True
        # TODO bleak address as _bleio.Address()

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value
        # TODO

    def start_advertising(
        self,
        data: Union[bytes, bytearray],
        *,
        scan_response: Union[bytes, bytearray] = None,
        connectable: bool = True,
        interval: float = 0.1
    ) -> None:
        # TODO
        pass

    def stop_advertising(self) -> None:
        """Stop sending advertising packets."""
        # TODO


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

        # Create a new event loop to do the scanning.
        # It will run in a separate thread.
        scan_thread = Thread(target=self._start_scan_async, args=(timeout,))
        scan_thread.start()

        # Wait for queue creation.
        while not self._scan_results_queue:
            pass

        return iter(self._scan_results_queue.sync_q.get, None)

        # while True:
        #     scan_entry = self._scan_results_queue.sync_q.get()
        #     if scan_entry:
        #         yield scan_entry
        #     else:
        #         # Terminate when None is received.

        #         raise StopIteration

    def _start_scan_async(self, timeout):
        asyncio.run(self._scantest(timeout))

    async def _scantest(self, timeout):
        self._scan_results_queue = janus.Queue()
        start = time.time()
        i = 0
        while time.time() - start < timeout:
            await asyncio.sleep(1)
            i += 1
            await self._scan_results_queue.async_q.put(i)
        await self._scan_results_queue.async_q.put(None)


    async def _scan(self, timeout: float) -> None:
        """
        Run as a task to scan and add ScanEntry objects to the queue.
        Repeat until stopped if timeout is None.
        """
        # If timeout is forever, do it in chunks.
        scan_timeout = 5.0 if timeout is None else timeout

        print("entering _scan loop")
        while self._scanning_in_progress:
            devices = await BleakScanner.discover(timeout=scan_timeout)
            print("discover results", devices)
            for device in devices:
                # Convert bleak scan result to a ScanEntry and save it.
                if device is not None:
                    # TODO: filter results
                    await self._scan_results_queue.put(_bleio.ScanEntry(device))
            if timeout is not None:
                # Repeat scan only if no timeout given.
                break
        self._scanning_in_progress = False
        print("exit _scan loop")

        # Add sentinel end iteration value to queue, and finish task.
        self._scan_results_queue.put(None)

    def stop_scan(self) -> None:
        self._scanning_in_progress = False

    @property
    def connected(self):
        # TODO
        return False

    @property
    def connections(self) -> Iterable:
        # TODO
        return ()

    def connect(self, address: _bleio.Address, *, timeout: Union[float, int]) -> None:
        # TODO
        pass

    def erase_bonding(self) -> None:
        # TODO
        pass
