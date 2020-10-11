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
`_bleio.address`
=======================================================================

`_bleio` for Blinka based on ``bleak``

* Author(s): Dan Halbert
"""

from __future__ import annotations
from typing import Any, Union

import re

Buf = Union[bytes, bytearray, memoryview]

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"


class Address:
    PUBLIC = 0x0
    RANDOM_STATIC = 0x1
    RANDOM_PRIVATE_RESOLVABLE = 0x2
    RANDOM_PRIVATE_NON_RESOLVABLE = 0x3

    _MAC_ADDRESS_RE = re.compile(r"[-:]".join([r"([0-9a-fA-F]{2})"] * 6))

    def __init__(
        self, address: Buf = None, address_type: int = RANDOM_STATIC, string: str = None
    ):
        """Bleak uses strings for addresses. The string may be a 6-byte MAC address,
        or it may be a UUID on MacOS."""

        self._address_bytes = None
        self._string = None

        if (address and string) or (not address and not string):
            raise ValueError("Supply address or string but not both:")
        if address:
            self._address_bytes = bytes(address)
            if len(self._address_bytes) != 6:
                raise ValueError("Address must be 6 bytes long")
        elif string:
            self._string = string
        if not self.PUBLIC <= address_type <= self.RANDOM_PRIVATE_NON_RESOLVABLE:
            raise ValueError("Address type out of range")
        self._type = address_type

    @property
    def _bleak_address(self) -> str:
        return self.string

    @property
    def string(self) -> str:
        """Original string, or if not given, address in "xx:xx:xx:xx:xx:xx" format."""
        if not self._string:
            self._string = ":".join(
                "{:02x}".format(b) for b in reversed(self.address_bytes)
            )
        return self._string

    @property
    def address_bytes(self) -> Buf:
        """bytes representation of MAC address. If address is a UUID (true on MacOS),
        raise ValueError.
        """
        if not self._address_bytes:
            # Attempt to convert to address bytes.
            match = self._MAC_ADDRESS_RE.fullmatch(self._string)
            if match:
                self._address_bytes = bytes(
                    int(b, 16) for b in reversed(match.groups())
                )
            else:
                raise ValueError("address_bytes not available; use self.string")
        return self._address_bytes

    @property
    def type(self) -> int:
        """Address type."""
        return self._type

    def __eq__(self, other: Any) -> bool:
        """True if addresses are equivalent."""
        if isinstance(other, Address):
            if self.type != other.type:
                return False
            if self._address_bytes:
                return self.address_bytes == other.address_bytes
            if self._string:
                return self._string == other._string
        return False

    def __hash__(self) -> int:
        return hash(self.string) ^ hash(self.type)

    def __repr__(self) -> str:
        return f'Address(string="{self.string}")'
