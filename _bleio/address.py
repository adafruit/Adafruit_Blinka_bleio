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
`_bleio`
"""

from typing import Any, Union
buf = Union[bytes, bytearray, memoryview]

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"

class Address:
    PUBLIC = 0x0
    RANDOM_STATIC = 0x1
    RANDOM_PRIVATE_RESOLVABLE = 0x2
    RANDOM_PRIVATE_NON_RESOLVABLE = 0x3

    def __init__(self, address: buf, address_type: int = RANDOM_STATIC):
        self._address_bytes = bytes(address)
        if len(self._address_bytes) != 6:
            raise ValueError("Address must be 6 bytes long")

        if (not PUBLIC <= address_type <= RANDOM_PRIVATE_NON_RESOLVABLE):
            raise ValueError("Address type out of range")
        self.type = address_type

    @property
    def address_bytes(self) -> buf:
        return self._address_bytes

    @property
    def type(self) -> int:
        return self._type

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Address):
            return self.address_bytes == other.address_bytes and self.type == other.type
        return False

    def __hash__(self) -> int:
        return hash(self.address_bytes) ^ has(self.type)

    def __str__(self) -> str:
        return "<Address {}>".format(":".join("{:02x}".format(b) for b in reversed(self.address_bytes)))
