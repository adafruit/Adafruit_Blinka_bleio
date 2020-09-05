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
`_bleio.uuid_`
=======================================================================

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries

"""
from __future__ import annotations
from typing import Any, Union

import re

Buf = Union[bytes, bytearray, memoryview]

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", flags=re.IGNORECASE
)

_STANDARD_UUID_RE = re.compile(
    r"0000....-0000-1000-8000-00805f9b34fb", flags=re.IGNORECASE
)

_STANDARD_HEX_UUID_RE = re.compile(r"[0-9a-f]{1,4}", flags=re.IGNORECASE)

_BASE_STANDARD_UUID = (
    b"\xFB\x34\x9B\x5F\x80\x00\x00\x80\x00\x10\x00\x00\x00\x00\x00\x00"
)


class UUID:
    def __init__(self, uuid: Union[int, Buf, str]):
        self.__bleak_uuid = None

        if isinstance(uuid, str):
            if _UUID_RE.fullmatch(uuid):
                self._size = 16 if _STANDARD_UUID_RE.fullmatch(uuid) else 128
                uuid = uuid.replace("-", "")
                self._uuid128 = bytes(
                    int(uuid[i : i + 2], 16) for i in range(30, -1, -2)
                )
                return

            if _STANDARD_HEX_UUID_RE.fullmatch(uuid):
                # Fall through and reprocess as an int.
                uuid = int(uuid, 16)
            else:
                raise ValueError(
                    "UUID string not 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' or 'xxxx', but is "
                    + uuid
                )

        if isinstance(uuid, int):
            if not 0 <= uuid <= 0xFFFF:
                raise ValueError("UUID integer value must be 0-0xffff")
            self._size = 16
            self._uuid16 = uuid
            # Put into "0000xxxx-0000-1000-8000-00805F9B34FB"
            self._uuid128 = bytes(
                (
                    0xFB,
                    0x34,
                    0x9B,
                    0x5F,
                    0x80,
                    0x00,  # 00805F9B34FB
                    0x00,
                    0x80,  # 8000
                    0x00,
                    0x10,  # 1000
                    0x00,
                    0x00,  # 0000
                    uuid & 0xFF,
                    (uuid >> 8) & 0xFF,  # xxxx
                    0x00,
                    0x00,
                )
            )  # 0000
        else:
            try:
                uuid = memoryview(uuid)
            except TypeError:
                raise ValueError(
                    "UUID value is not str, int or byte buffer"
                ) from TypeError
            if len(uuid) != 16:
                raise ValueError("Byte buffer must be 16 bytes")
            self._size = 128
            self._uuid128 = bytes(uuid)

    @classmethod
    def _from_bleak(cls, bleak_uuid: Any) -> "UUID":
        """Convert a bleak UUID to a _bleio.UUID."""
        uuid = UUID(bleak_uuid)
        uuid.__bleak_uuid = bleak_uuid  # pylint: disable=protected-access
        return uuid

    @property
    def _bleak_uuid(self):
        """Bleak UUID"""
        if not self.__bleak_uuid:
            self.__bleak_uuid = str(self)
        return self.__bleak_uuid

    @property
    def uuid16(self) -> int:
        if self.size == 128:
            raise ValueError("This is a 128-bit UUID")
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

    @property
    def is_standard_uuid(self):
        """True if this is a standard 16-bit UUID (0000xxxx-0000-1000-8000-00805F9B34FB)
        even if it's 128-bit."""
        return self.size == 16 or (
            self._uuid128[0:12] == _BASE_STANDARD_UUID[0:12]
            and self._uuid128[14:] == _BASE_STANDARD_UUID[14:]
        )

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, UUID):
            if self.size == 16 and other.size == 16:
                return self.uuid16 == other.uuid16
            if self.size == 128 and other.size == 128:
                return self.uuid128 == other.uuid128

        return False

    def __hash__(self):
        if self.size == 16:
            return hash(self.uuid16)
        return hash(self.uuid128)

    def __str__(self) -> str:
        return (
            "{:02x}{:02x}{:02x}{:02x}-"
            "{:02x}{:02x}-"
            "{:02x}{:02x}-"
            "{:02x}{:02x}-"
            "{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}"
        ).format(*reversed(self.uuid128))

    def __repr__(self) -> str:
        if self.size == 16:
            return "UUID({:#04x})".format(self.uuid16)
        return "UUID({})".format(str(self))


UUID.BASE_STANDARD_UUID = UUID("00000000-0000-1000-8000-00805F9B34FB")
"""16 bit xxyy UUIDs are shorthand for the
base 128-bit UUID 0000yyxx-0000-1000-8000-00805F9B34FB."""
