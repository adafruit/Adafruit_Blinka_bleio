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
`_bleio.service`
=======================================================================

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""
from __future__ import annotations
from typing import Tuple, Union

from bleak.backends.service import BleakGATTService

from _bleio.characteristic import Characteristic
import _bleio.connection
from _bleio.uuid_ import UUID


class Service:
    """Stores information about a BLE service and its characteristics."""

    def __init__(
        self,
        uuid: UUID,
        *,
        secondary: bool = False,
        remote: bool = False,
    ):
        """Create a new Service identified by the specified UUID. It can be accessed by all
        connections. This is known as a Service server. Client Service objects are created via
        `_bleio.Connection.discover_remote_services`.

        To mark the Service as secondary, pass `True` as :py:data:`secondary`.

        :param UUID uuid: The uuid of the service
        :param bool secondary: If the service is a secondary one

        :return: the new Service
        """
        self._uuid = uuid
        self._secondary = secondary
        self._remote = remote
        self._connection = None
        self._characteristics = ()
        self._bleak_gatt_service = None

    # pylint: disable=protected-access
    @classmethod
    def _from_bleak(
        cls,
        connection: _bleio.connection.Connection,
        bleak_gatt_service: BleakGATTService,
    ) -> Service:
        service = cls(UUID(bleak_gatt_service.uuid), remote=True)
        service._connection = connection
        service._characteristics = tuple(
            Characteristic._from_bleak(service, bleak_characteristic)
            for bleak_characteristic in bleak_gatt_service.characteristics
        )
        service._bleak_gatt_service = bleak_gatt_service
        return service

    @property
    def _bleak_service(self):
        """BleakGATTService object"""
        return self._bleak_gatt_service

    @property
    def characteristics(self) -> Tuple[Characteristic]:
        """A tuple of :py:class:`Characteristic` designating the characteristics that are offered by
        this service. (read-only)"""
        return self._characteristics

    @property
    def remote(self) -> bool:
        """True if this is a service provided by a remote device. (read-only)"""
        return self._remote

    @property
    def secondary(self) -> bool:
        """True if this is a secondary service. (read-only)"""
        return self._secondary

    @property
    def uuid(self) -> Union[UUID, None]:
        """The UUID of this service. (read-only)
        Will be ``None`` if the 128-bit UUID for this service is not known.
        """
        return self._uuid

    @property
    def connection(self) -> _bleio.connection.Connection:
        """Connection associated with this service, if any."""
        return self._connection

    def __repr__(self) -> str:
        if self.uuid:
            return f"<Service: {self.uuid}>"
        return "<Service: uuid is None>"
