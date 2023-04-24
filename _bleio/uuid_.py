# SPDX-FileCopyrightText: Copyright (c) 2020 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT

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

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", flags=re.IGNORECASE
)

_STANDARD_UUID_RE_16 = re.compile(
    r"0000....-0000-1000-8000-00805f9b34fb", flags=re.IGNORECASE
)

_STANDARD_UUID_RE_32 = re.compile(
    r"........-0000-1000-8000-00805f9b34fb", flags=re.IGNORECASE
)

_STANDARD_HEX_UUID_RE = re.compile(r"[0-9a-f]{1,8}", flags=re.IGNORECASE)

_BASE_STANDARD_UUID = (
    b"\xFB\x34\x9B\x5F\x80\x00\x00\x80\x00\x10\x00\x00\x00\x00\x00\x00"
)


class UUID:
    @staticmethod
    def standard_uuid128_from_uuid32(uuid32: int) -> bytes:
        """Return a 128-bit standard UUID from a 32-bit standard UUID."""
        if not 0 <= uuid32 < 2**32:
            raise ValueError("UUID integer value must be unsigned 32-bit")
        return _BASE_STANDARD_UUID[:-4] + uuid32.to_bytes(4, "little")

    @staticmethod
    def _init_from_str(uuid: str) -> tuple[bytes, int]:
        if _UUID_RE.fullmatch(uuid):
            # Pick the smallest standard size.
            if _STANDARD_UUID_RE_16.fullmatch(uuid):
                size = 16
                uuid16 = int(uuid[4:8], 16)
                uuid128 = UUID.standard_uuid128_from_uuid32(uuid16)
                return uuid128, size

            if _STANDARD_UUID_RE_32.fullmatch(uuid):
                size = 32
                uuid32 = int(uuid[0:8], 16)
                uuid128 = UUID.standard_uuid128_from_uuid32(uuid32)
                return uuid128, size

            size = 128
            uuid = uuid.replace("-", "")
            uuid128 = bytes(int(uuid[i : i + 2], 16) for i in range(30, -1, -2))
            return uuid128, size

        if _STANDARD_HEX_UUID_RE.fullmatch(uuid) and len(uuid) in (4, 8):
            # Fall through and reprocess as an int.
            uuid_int = int(uuid, 16)
            size = len(uuid) * 4  # 4 bits per hex digit
            uuid128 = UUID.standard_uuid128_from_uuid32(uuid_int)
            return uuid128, size

        raise ValueError(
            "UUID string not 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',"
            "'xxxx', or 'xxxxxxxx', but is " + uuid
        )

    @staticmethod
    def _init_from_int(uuid: int) -> tuple[bytes, int]:
        if not 0 <= uuid <= 2**32:
            raise ValueError("UUID integer value must be unsigned 16- or 32-bit")
        if uuid <= 2**16:
            size = 16
        if uuid <= 2**32:
            size = 32
        uuid128 = UUID.standard_uuid128_from_uuid32(uuid)
        return uuid128, size

    @staticmethod
    def _init_from_buf(uuid: Buf) -> tuple[bytes, int]:
        try:
            uuid = memoryview(uuid)
        except TypeError:
            raise ValueError("UUID value is not str, int or byte buffer") from TypeError
        if len(uuid) != 16:
            raise ValueError("Byte buffer must be 16 bytes")
        size = 128
        uuid128 = bytes(uuid)
        return uuid128, size

    def __init__(self, uuid: Union[int, Buf, str]):
        self.__bleak_uuid = None

        if isinstance(uuid, str):
            self._uuid128, self._size = self._init_from_str(uuid)

        elif isinstance(uuid, int):
            self._uuid128, self._size = self._init_from_int(uuid)

        else:
            self._uuid128, self._size = self._init_from_buf(uuid)

    @classmethod
    def _from_bleak(cls, bleak_uuid: Any) -> "UUID":
        """Convert a bleak UUID to a _bleio.UUID."""
        uuid = UUID(bleak_uuid)
        uuid.__bleak_uuid = bleak_uuid  # pylint: disable=unused-private-member
        return uuid

    @property
    def _bleak_uuid(self):
        """Bleak UUID"""
        if not self.__bleak_uuid:
            self.__bleak_uuid = str(self)
        return self.__bleak_uuid

    @property
    def uuid16(self) -> int:
        if self.size > 16:
            raise ValueError(f"This is a {self.size}-bit UUID")
        return int.from_bytes(self._uuid128[12:14], "little")

    @property
    def uuid32(self) -> int:
        if self.size > 32:
            raise ValueError(f"This is a {self.size}-bit UUID")
        return int.from_bytes(self._uuid128[12:], "little")

    @property
    def uuid128(self) -> bytes:
        return self._uuid128

    @property
    def size(self) -> int:
        return self._size

    def pack_into(self, buffer, offset=0) -> None:
        byte_size = self.size // 8
        if len(buffer) - offset < byte_size:
            raise IndexError("Buffer offset too small")
        if self.size == 16:
            buffer[offset:byte_size] = self.uuid128[12:14]
        elif self.size == 32:
            buffer[offset:byte_size] = self.uuid128[12:]
        else:
            buffer[offset:byte_size] = self.uuid128

    @property
    def is_standard_uuid(self) -> bool:
        """True if this is a standard 16 or 32-bit UUID (xxxxxxxx-0000-1000-8000-00805F9B34FB)
        even if it's 128-bit."""
        return (
            self.size == 16
            or self.size == 32
            or (
                self._uuid128[0:12] == _BASE_STANDARD_UUID[0:12]
                and self._uuid128[14:] == _BASE_STANDARD_UUID[14:]
            )
        )

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, UUID):
            if self.size == 16 and other.size == 16:
                return self.uuid16 == other.uuid16
            if self.size == 32 and other.size == 32:
                return self.uuid32 == other.uuid32
            if self.size == 128 and other.size == 128:
                return self.uuid128 == other.uuid128

        return False

    def __hash__(self):
        if self.size == 16:
            return hash(self.uuid16)
        if self.size == 32:
            return hash(self.uuid32)
        return hash(self.uuid128)

    def __str__(self) -> str:
        return (
            "{:02x}{:02x}{:02x}{:02x}-"  # pylint: disable=consider-using-f-string
            "{:02x}{:02x}-"
            "{:02x}{:02x}-"
            "{:02x}{:02x}-"
            "{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}"
        ).format(*reversed(self.uuid128))

    def __repr__(self) -> str:
        if self.size == 16:
            return f"UUID({self.uuid16:#04x})"
        if self.size == 32:
            return f"UUID({self.uuid32:#08x})"
        return f"UUID({self!s})"
