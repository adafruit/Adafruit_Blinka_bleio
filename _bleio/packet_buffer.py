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
`_bleio.packet_buffer`
=======================================================================

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""
import queue
from typing import Union

from _bleio import Characteristic

Buf = Union[bytes, bytearray, memoryview]


class PacketBuffer:
    """Accumulates a Characteristic's incoming packets in a FIFO buffer and facilitates packet aware
    outgoing writes. A packet's size is either the characteristic length or the maximum transmission
    unit (MTU) minus overhead, whichever is smaller. The MTU can change so check
    `incoming_packet_length` and `outgoing_packet_length` before creating a buffer to store data.

    When we're the server, we ignore all connections besides the first to subscribe to
    notifications."""

    def __init__(self, characteristic: Characteristic, *, buffer_size: int):
        """Monitor the given Characteristic. Each time a new value is written to the Characteristic
        add the newly-written bytes to a FIFO buffer.

        :param Characteristic characteristic: The Characteristic to monitor.
          It may be a local Characteristic provided by a Peripheral Service,
          or a remote Characteristic in a remote Service that a Central has connected to.
        :param int buffer_size: Size of ring buffer (in packets of the Characteristic's maximum
          length) that stores incoming packets coming from the peer."""
        self._queue = queue.Queue(buffer_size)
        self._characteristic = characteristic
        characteristic._add_notify_callback(self._notify_callback)

    def _notify_callback(self, data: Buf) -> None:
        if self._queue.full():
            # Discard oldest data to make room.
            self._queue.get_nowait()
        self._queue.put_nowait(data)

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

    def write(self, data: Buf, *, header: Union[Buf, None] = None) -> int:
        """Writes all bytes from data into the same outgoing packet.
        The bytes from header are included before data when the pending packet is currently empty.

        This does not block until the data is sent. It only blocks until the data is pending.

        :return: number of bytes written. May include header bytes when packet is empty.
        :rtype: int
        """
        # Unlike in native _bleio, we cannot merge outgoing packets while waiting
        # for a pending packet to be sent. So just sent the packets with a full header,
        # one at a time.
        packet = header + data if header else data
        self._characteristic.value = packet
        return len(packet)

    def deinit(self) -> None:
        """Disable permanently."""
        self._characteristic.remove_notify_callback(self._notify_callback)

    @property
    def packet_size(self) -> int:
        """`packet_size` is the same as `incoming_packet_length`.
        The name `packet_size` is deprecated and
        will be removed in CircuitPython 6.0.0."""
        return self.incoming_packet_length

    @property
    def incoming_packet_length(self) -> int:
        """Maximum length in bytes of a packet we are reading."""
        return 512

    @property
    def outgoing_packet_length(self):
        """Maximum length in bytes of a packet we are writing."""
        return 512
