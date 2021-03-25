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

# pylint: disable=redefined-builtin
from _bleio.address import Address
from _bleio.attribute import Attribute
from _bleio.characteristic_buffer import CharacteristicBuffer
from _bleio.common import adapter, Adapter, Characteristic, Connection, Service
from _bleio.exceptions import (
    BluetoothError,
    ConnectionError,
    RoleError,
    SecurityError,
)
from _bleio.packet_buffer import PacketBuffer
from _bleio.scan_entry import ScanEntry
from _bleio.uuid_ import UUID

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"


def set_adapter(new_adapter: Optional[Adapter]) -> None:
    """Set the adapter to use for BLE, such as when using an HCI adapter.
    Raises `NotImplementedError` when the adapter is a singleton and cannot be set.
    """
    raise NotImplementedError("Not settable")
