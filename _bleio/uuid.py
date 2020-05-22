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

import re
from typing import Any, Union
buf = Union[bytes, bytearray, memoryview]

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"

_UUID_RE = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")

class UUID:
    def __init__(self, uuid: Union[int, buf, str]):
        if isinstance(uuid, int):
            if not (0 <= uuid <= 0xffff):
                raise ValueError("UUID integer value must be 0-0xffff")
            self._size = 16
            self._uuid16 = uuid
            # Put into "0000xxxx-0000-1000-8000-00805F9B34FB"
            self._uuid128 = (0xFB, 0x34, 0x9B, 0x5F, 0x80, 0x00, # 00805F9B34FB
                             0x00, 0x80, # 8000
                             0x00, 0x10, # 1000
                             0x00, 0x00, # 0000
                             uuid & 0xff, (uuid >> 8) & 0xff, # xxxx
                             0x00, 0x00) # 0000
        elif isinstance(uuid, str):
            if _UUID_RE.match(uuid):
                self._size = 128
                uuid = uuid.replace("-", "")
                self._uuid128 = bytes(int(uuid[i:i+2], 16) for i in range(30, -1, -2))
            else:
                raise ValueError("UUID string not 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'")
        else:
            try:
                uuid = memoryview(uuid)
            except TypeError:
                raise ValueError("UUID value is not str, int or byte buffer")
            if len(uuid) != 16:
                raise ValueError("Byte buffer must be 16 bytes")
            self._uuid128 = bytes(uuid)

    @property
    def uuid16(self) -> int:
        return (self._uuid128[13] << 8) | self._uuid128[12]

    @property
    def uuid128(self) -> bytes:
        return self._uuid128

    @property
    def size(self) -> int:
        return self._size

    def pack_into(self, buffer, offset=0):
        byte_size = self.size // 8
        if len(buffer) - offset < byte_size:
            raise IndexError("Buffer offset too small")
        if self.size == 16:
            buffer[offset:byte_size] = self.uuid128[12:14]
        else:
            buffer[offset:byte_size] = self.uuid128

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, UUID):
            if self.size == 16 and other.size == 16:
                return self.uuid16 == other.uuid16
            if self.size == 128 and other.size ==128:
                return self.uuid128 == other.uuid128

        return False

    def __str__(self) -> str:
        if self.size == 16:
            return "UUID({:#04x})".format(self.uuid16)
        else:
            return ('UUID("{:02x}{:02x}{:02x}{:02x}-'
                    "{:02x}{:02x}-"
                    "{:02x}{:02x}-"
                    "{:02x}{:02x}-"
                    '{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}")').format(*reversed(self.uuid128))
