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
`_bleio.characteristic_buffer`
=======================================================================

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""
from __future__ import annotations
from typing import Union

import asyncio
import queue
import time

import _bleio.adapter_ as adap
from _bleio.characteristic import Characteristic

Buf = Union[bytes, bytearray, memoryview]


class CharacteristicBuffer:
    """Accumulates a Characteristic's incoming values in a FIFO buffer."""

    def __init__(
        self,
        characteristic: Characteristic,
        *,
        timeout: float = 1,
        buffer_size: int = 64
    ):

        """Monitor the given Characteristic. Each time a new value is written to the Characteristic
        add the newly-written bytes to a FIFO buffer.

        :param Characteristic characteristic: The Characteristic to monitor.
          It may be a local Characteristic provided by a Peripheral Service,
          or a remote Characteristic in a remote Service that a Central has connected to.
        :param int timeout:  the timeout in seconds to wait for the first character
          and between subsequent characters.
        :param int buffer_size: Size of ring buffer that stores incoming data coming from client.
          Must be >= 1."""
        self._characteristic = characteristic
        self._timeout = timeout
        self._buffer_size = buffer_size
        self._queue = queue.Queue(buffer_size)
        characteristic._add_notify_callback(self._notify_callback)

    def _notify_callback(self, data: Buf) -> None:
        # Add data bytes to queue, one at a time.
        if self._queue.full():
            # Discard oldest data to make room.
            while self._queue.qsize() > len(data):
                self._queue.get_nowait()

        for b in data:
            try:
                self._queue.put_nowait(b)
            except queue.Full:
                return

    def read(self, nbytes: int = None) -> Union[Buf, None]:
        """Read characters.  If ``nbytes`` is specified then read at most that many
        bytes. Otherwise, read everything that arrives until the connection
        times out. Providing the number of bytes expected is highly recommended
        because it will be faster.

        :return: Data read
        """
        b = bytearray(min(nbytes, self._buffer_size) if nbytes else self._buffer_size)
        if self.readinto(b) == 0:
            return None
        return b

    def readinto(self, buf: Buf) -> Union[int, None]:
        """Read bytes into the ``buf``. Read at most ``len(buf)`` bytes.

        :return: number of bytes read and stored into ``buf``
        """
        length = len(buf)
        idx = 0
        end = time.time() + self._timeout
        while idx < length and time.time() < end:
            try:
                buf[idx] = self._queue.get_nowait()
                idx += 1
            except queue.Empty:
                # Let the BLE code run for a bit, and try again.
                adap.adapter.await_bleak(asyncio.sleep(0.1))

        return idx

    def readline(self,) -> Buf:
        """Read a line, ending in a newline character.

        :return: the line read
        """
        line = bytearray()
        end = time.time() + self._timeout
        while time.time() < end:
            try:
                b = self._queue.get_nowait()
                line.append(b)
            except queue.Empty:
                # Let the BLE code run for a bit, and try again.
                adap.adapter.await_bleak(asyncio.sleep(0.1))
            if b == 0x0A:  # newline
                break

        return line

    @property
    def in_waiting(self) -> int:
        """The number of bytes in the input buffer, available to be read"""
        return self._queue.qsize()

    def reset_input_buffer(self,) -> None:
        """Discard any unread characters in the input buffer."""
        while not self._queue.empty():
            self._queue.get_nowait()

    def deinit(self,) -> None:
        """Disable permanently."""
        # pylint: disable=protected-access
        self._characteristic._remove_notify_callback(self._notify_callback)
