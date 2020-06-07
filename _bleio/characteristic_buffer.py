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
from collections import deque
import queue
from __future__ import annotations
from typing import Union

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
          It may be a local Characteristic provided by a Peripheral Service, or a remote Characteristic
          in a remote Service that a Central has connected to.
        :param int timeout:  the timeout in seconds to wait for the first character and between subsequent characters.
        :param int buffer_size: Size of ring buffer that stores incoming data coming from client.
          Must be >= 1."""
        self._characteristic = characteristic
        self._timeout = timeout
        self._queue = queue.Queue(buffer_size)
        characteristic.notify_queue = self._queue

    def read(self, nbytes: int = None) -> Union[Buf, None]:
        """Read characters.  If ``nbytes`` is specified then read at most that many
        bytes. Otherwise, read everything that arrives until the connection
        times out. Providing the number of bytes expected is highly recommended
        because it will be faster.

        :return: Data read
        :rtype: bytes or None
        """
        b = bytearray()
        start = time.time()
        end = time.time() + self._timeout
        while time.time() < end and len(b) < nbytes:
            try:
                b.extend(self._queue.get_nowait())
            except queue.Empty:
                # Let the BLE code run for a bit, and try again.
                adap.adapter.await_bleak(asyncio.sleep(0.1))
        return b

    def readinto(self, buf: Buf) -> Union[int, None]:
        """Read bytes into the ``buf``. Read at most ``len(buf)`` bytes.

        :return: number of bytes read and stored into ``buf``
        :rtype: int or None (on a non-blocking error)"""
        bytes_read = self.read(nbytes, len(buf))
        buf[0 : len(bytes_read)] = bytes_read

    def readline(self,) -> Buf:
        """Read a line, ending in a newline character.

        :return: the line read
        :rtype: int or None"""
        b = bytearray()
        start = time.time()
        end = time.time() + self._timeout
        while time.time() < end:
            try:
                chars = self._queue.get_nowait()
                newline = chars.find(0x0A)
                if newline != -1:
                    b.extend(self._queue.get_nowait())
            except queue.Empty:
                # Let the BLE code run for a bit, and try again.
                adap.adapter.await_bleak(asyncio.sleep(0.1))
        return b

    in_waiting: Any = ...
    """The number of bytes in the input buffer, available to be read"""

    def reset_input_buffer(self,) -> Any:
        """Discard any unread characters in the input buffer."""
        while not self._queue.empty():
            self._queue.get_nowait()

    def deinit(self,) -> Any:
        """Disable permanently."""

    def readinto(self, buf: Buf) -> int:
        """Reads a single BLE packet into the ``buf``.
        Raises an exception if the next packet is longer than the given buffer.
        Use `packet_size` to read the maximum length of a single packet.

        :return: number of bytes read and stored into ``buf``
        :rtype: int
        """
        if self._queue.empty():
            return 0
        packet = self._queue.get_nowait()
        packet_len = len(packet)
        buf_len = len(buf)

        if packet_len > buf_len:
            # Return negative of overrun value. Don't write anything.
            return buf_len - packet_len
        buf[0:packet_len] = packet
        return packet_len
