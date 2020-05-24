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
from threading import Thread
import time

# janus.Queue is thread-safe and can be used from both sync and async code.
import janus
from bleak import discover

import _bleio


class Adapter:
    def __init__(self):
        if _bleio.adapter:
            return _bleio.adapter
        self._name = "TODO"
        # Unbounded FIFO for scan results
        self._scan_queue = None
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
            else:
                yield scan_entry

    def stop_scan(self) -> None:
        self._scanning_in_progress = False
        # Drain the queue of any unread entries.
        # The last entry will be a None.
        while self._next_from_queue() is not None:
            pass

    def _next_from_queue(self) -> Any:
        """Read next item from scan entry queue. When done, clean up and return None."""
        q = self._scan_queue
        scan_entry = q.sync_q.get()
        # Tell producer we read the entry. This allows clean shutdown when done.
        q.sync_q.task_done()

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
        q = self._scan_queue = janus.Queue()

        # If timeout is forever, do it in chunks.

        # The bleak discover(timeout) is the total time to spend scanning.
        # No intermediate results are returned during the timeout period,
        # unlike _bleio.start_scan(). So scan in short increments to emulate
        # returning intermediate results.

        start = time.time()
        bleak_timeout = min(timeout, 0.25)

        while self._scanning_in_progress:
            devices = await discover(timeout=bleak_timeout)
            for device in devices:
                # Convert bleak scan result to a ScanEntry and save it.
                if device is not None:
                    # TODO: filter results
                    await q.async_q.put(_bleio.ScanEntry(device))
            if timeout is not None and time.time() - start > timeout:
                # Quit when timeout period has elapsed.
                break

        # Finished scanning.
        # Put sentinel end iteration value on queue.
        await q.async_q.put(None)

        # Wait for queue to be emptied.
        await q.async_q.join()
        q.close()
        await q.wait_closed()


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
