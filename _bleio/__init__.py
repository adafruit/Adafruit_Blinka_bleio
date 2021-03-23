# SPDX-FileCopyrightText: Copyright (c) 2020 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`_bleio`
=======================================================================

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""

# pylint: disable=wrong-import-position

from typing import Optional

# These are in dependency order to avoid circular import issues.

from _bleio.exceptions import *  # pylint: disable=redefined-builtin
from _bleio.uuid_ import *
from _bleio.address import *
from _bleio.adapter_ import *
from _bleio.attribute import *
from _bleio.characteristic import *
from _bleio.service import *
from _bleio.connection import *
from _bleio.descriptor import *
from _bleio.scan_entry import *

from _bleio.characteristic_buffer import *
from _bleio.packet_buffer import *


def set_adapter(new_adapter: Optional[Adapter]) -> None:
    """Set the adapter to use for BLE, such as when using an HCI adapter.
    Raises `NotImplementedError` when the adapter is a singleton and cannot be set.
    """
    raise NotImplementedError("Not settable")


__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"
