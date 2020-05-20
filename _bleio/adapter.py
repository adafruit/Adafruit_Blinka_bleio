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

import asyncio

import _bleio
from bleak import discover

class Adapter:
    def __init__(self):
        if _bleio.adapter:
            raise NotImplementedError(
                """You cannot create an instance of _bleio.Adapter.
                Use _bleio.adapter` to access the sole instance available.
                """)
        self._name = TODO
        # Unbounded FIFO for scan results
        self._scan_results_queue = asyncio.Queue()


    @property
    def enabled(self) -> bool:
        return // TODO bleak enable/disable

    @enabled.setter
    def enabled(self, value: bool):
        // TODO bleak enable/disable


    @property
    def address(self) -> _bleio.Address:
        self._enable(True)
        return // TODO bleak address as Address()

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value
        TODO // set name in bleak


    def start_advertising(self, data: buf, *, scan_response: buf = None, connectable: bool = True, interval: float = 0.1) -> Any:
        TODO

    def stop_advertising(self, ) -> Any:
        """Stop sending advertising packets."""
        TODO

    def start_scan(self, prefixes: sequence = b"", *, buffer_size: int = 512, extended: bool = False, timeout: float = None, interval: float = 0.1, window: float = 0.1, minimum_rssi: int = -80, active: bool = True) -> Any:
        """Starts a BLE scan and returns an iterator of results. Advertisements and scan responses are
        filtered and returned separately.

        :param sequence prefixes: Sequence of byte string prefixes to filter advertising packets
            with. A packet without an advertising structure that matches one of the prefixes is
            ignored. Format is one byte for length (n) and n bytes of prefix and can be repeated.
        :param int buffer_size: the maximum number of advertising bytes to buffer.
        :param bool extended: When True, support extended advertising packets. Increasing buffer_size is recommended when this is set.
        :param float timeout: the scan timeout in seconds. If None, will scan until `stop_scan` is called.
        :param float interval: the interval (in seconds) between the start of two consecutive scan windows
           Must be in the range 0.0025 - 40.959375 seconds.
        :param float window: the duration (in seconds) to scan a single BLE channel.
           window must be <= interval.
        :param int minimum_rssi: the minimum rssi of entries to return.
        :param bool active: retrieve scan responses for scannable advertisements.
        :returns: an iterable of `_bleio.ScanEntry` objects
        :rtype: iterable"""

        internal_timeout = 5 if timeout is None else timeout

        await asyncio.sleep(internal_timeout)
        devices = await scanner.get_discovered_devices()
        for d in devices:
            TODO add to queue. if timeout=None, keep repeating. Notice if stop_scan().


    async def _scan(self, timeout):
        async with BleakScanner(timeout=timeout) as scanner:


    def stop_scan(self, ) -> Any:
        """Stop the current scan."""
        TODO

    connected: Any = ...
    """True when the adapter is connected to another device regardless of who initiated the
    connection. (read-only)"""

    connections: Any = ...
    """Tuple of active connections including those initiated through
    :py:meth:`_bleio.Adapter.connect`. (read-only)"""

    def connect(self, address: Address, *, timeout: float/int) -> Any:
        """Attempts a connection to the device with the given address.

        :param Address address: The address of the peripheral to connect to
        :param float/int timeout: Try to connect for timeout seconds."""
        TODO

    def erase_bonding(self, ):
        TODO
