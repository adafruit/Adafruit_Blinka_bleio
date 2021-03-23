# SPDX-FileCopyrightText: Copyright (c) 2020 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`_bleio.attribute`
================================================================================

`_bleio` for Blinka based on ``bleak``

* Author(s): Dan Halbert
"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"

from enum import Enum


class Attribute(Enum):
    NO_ACCESS = 0x00
    OPEN = 0x11
    ENCRYPT_NO_MITM = 0x21
    ENCRYPT_WITH_MITM = 0x31
    LESC_ENCRYPT_WITH_MITM = 0x41
    SIGNED_NO_MITM = 0x12
    SIGNED_WITH_MITM = 0x22
