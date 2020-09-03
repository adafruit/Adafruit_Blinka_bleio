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
`_bleio.characteristic`
=======================================================================

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""
from __future__ import annotations
from typing import Any, Callable, Tuple, Union

from bleak.backends.characteristic import (
    BleakGATTCharacteristic,
    GattCharacteristicsFlags,
)

import _bleio.adapter_ as adap
from _bleio.attribute import Attribute
from _bleio.uuid_ import UUID

Buf = Union[bytes, bytearray, memoryview]


class Characteristic:
    """Stores information about a BLE service characteristic and allows reading
       and writing of the characteristic's value."""

    BROADCAST = 0x1
    """property: allowed in advertising packets"""
    INDICATE = 0x2
    """property: server will indicate to the client when the value is set and wait for a response"""
    NOTIFY = 0x4
    """property: server will notify the client when the value is set"""
    READ = 0x8
    """property: clients may read this characteristic"""
    WRITE = 0x10
    """property: clients may write this characteristic; a response will be sent back"""
    WRITE_NO_RESPONSE = 0x20
    """property: clients may write this characteristic; no response will be sent back"""

    def __init__(
        self,
        *,
        uuid: UUID,
        properties: int = 0,
        read_perm: int = Attribute.OPEN,
        write_perm: int = Attribute.OPEN,
        max_length: int = 20,
        fixed_length: bool = False,
        initial_value: Buf = None
    ):
        """There is no regular constructor for a Characteristic.  A
        new local Characteristic can be created and attached to a
        Service by calling `add_to_service()`.  Remote Characteristic
        objects are created by `_bleio.Connection.discover_remote_services`
        as part of remote Services."""
        self._uuid = uuid
        self._properties = properties
        self._read_perm = read_perm
        self._write_perm = write_perm
        self._max_length = max_length
        self._fixed_length = fixed_length
        self._initial_value = initial_value
        self._service = None
        self._descriptors = ()
        self._bleak_gatt_characteristic = None
        self._notify_callbacks = set()

    @classmethod
    def add_to_service(
        cls,
        service: "Service",
        uuid: UUID,
        *,
        properties: int = 0,
        read_perm: int = Attribute.OPEN,
        write_perm: int = Attribute.OPEN,
        max_length: int = 20,
        fixed_length: bool = False,
        initial_value: Buf = None
    ) -> "Characteristic":
        """Create a new Characteristic object, and add it to this Service.

        :param Service service: The service that will provide this characteristic
        :param UUID uuid: The uuid of the characteristic
        :param int properties: The properties of the characteristic,
           specified as a bitmask of these values bitwise-or'd together:
           `BROADCAST`, `INDICATE`, `NOTIFY`, `READ`, `WRITE`, `WRITE_NO_RESPONSE`.
        :param int read_perm: Specifies whether the characteristic can be read by a client,
           and if so, which security mode is required.
           Must be one of the integer values `_bleio.Attribute.NO_ACCESS`, `_bleio.Attribute.OPEN`,
           `_bleio.Attribute.ENCRYPT_NO_MITM`, `_bleio.Attribute.ENCRYPT_WITH_MITM`,
           `_bleio.Attribute.LESC_ENCRYPT_WITH_MITM`,
           `_bleio.Attribute.SIGNED_NO_MITM`, or `_bleio.Attribute.SIGNED_WITH_MITM`.
        :param int write_perm: Specifies whether the characteristic can be written by a client,
           and if so, which security mode is required.
           Values allowed are the same as ``read_perm``.
        :param int max_length: Maximum length in bytes of the characteristic value.
           The maximum allowed is is 512, or possibly 510 if ``fixed_length`` is False.
           The default, 20, is the maximum number of data bytes
           that fit in a single BLE 4.x ATT packet.
        :param bool fixed_length: True if the characteristic value is of fixed length.
        :param buf initial_value: The initial value for this characteristic.
           If not given, will be filled with zeros.

        :return: the new Characteristic."""
        charac = Characteristic(
            uuid=uuid,
            properties=properties,
            read_perm=read_perm,
            write_perm=write_perm,
            max_length=max_length,
            fixed_length=fixed_length,
            initial_value=initial_value,
        )
        charac._service = service  # pylint: disable=protected-access
        return charac

    @classmethod
    def _from_bleak(
        cls, service: "Service", _bleak_characteristic: BleakGATTCharacteristic
    ):
        properties = 0
        for prop in _bleak_characteristic.properties:
            properties |= GattCharacteristicsFlags[prop.replace("-", "_")].value
        charac = Characteristic.add_to_service(
            service=service,
            uuid=UUID(_bleak_characteristic.uuid),
            properties=properties,
            read_perm=Attribute.OPEN,
            write_perm=Attribute.OPEN,
        )

        # pylint: disable=protected-access
        charac._bleak_gatt_characteristic = _bleak_characteristic
        # pylint: enable=protected-access
        return charac

    def _bleak_characteristic(self):
        """BleakGATTCharacteristic object"""
        return self._bleak_gatt_characteristic

    @property
    def properties(self) -> int:
        """An int bitmask representing which properties are set, specified as bitwise or'ing of
        of these possible values.
        `BROADCAST`, `INDICATE`, `NOTIFY`, `READ`, `WRITE`, `WRITE_NO_RESPONSE`.
    """
        return self._properties

    @property
    def uuid(self) -> UUID:
        """The UUID of this characteristic. (read-only)
        Will be ``None`` if the 128-bit UUID for this characteristic is not known."""
        return self._uuid

    @property
    def value(self) -> Union[bytes, None]:
        """The value of this characteristic."""
        return adap.adapter.await_bleak(
            # pylint: disable=protected-access
            self.service.connection._bleak_client.read_gatt_char(self.uuid._bleak_uuid)
        )

    @value.setter
    def value(self, val) -> None:
        adap.adapter.await_bleak(
            # BlueZ DBus cannot take a bytes here, though it can take a tuple, etc.
            # So use a bytearray.
            # pylint: disable=protected-access
            self.service.connection._bleak_client.write_gatt_char(
                self.uuid._bleak_uuid,
                bytearray(val),
                response=self.properties | Characteristic.WRITE,
            )
        )

    @property
    def descriptors(self) -> Tuple["Descriptor"]:
        """A tuple of :py:class:~`Descriptor` that describe this characteristic. (read-only)"""
        return self._descriptors

    @property
    def service(self) -> "Service":
        """The Service this Characteristic is a part of."""
        return self._service

    def set_cccd(self, *, notify: bool = False, indicate: bool = False) -> Any:
        """Set the remote characteristic's CCCD to enable or disable notification and indication.

        :param bool notify: True if Characteristic should receive notifications of remote writes
        :param float indicate: True if Characteristic should receive indications of remote writes
        """
        if indicate:
            raise NotImplementedError("Indicate not available")

        # pylint: disable=protected-access
        if notify:
            adap.adapter.await_bleak(
                self._service.connection._bleak_client.start_notify(
                    self._bleak_gatt_characteristic.uuid, self._notify_callback,
                )
            )
        else:
            adap.adapter.await_bleak(
                self._service._bleak_client.stop_notify(
                    self._bleak_gatt_characteristic.uuid
                )
            )

    def _add_notify_callback(self, callback: Callable[[Buf], None]):
        """Add a callback to call when a notify happens on this characteristic."""
        self._notify_callbacks.add(callback)

    def _remove_notify_callback(self, callback: Callable[[Buf], None]):
        """Remove a callback to call when a notify happens on this characteristic."""
        self._notify_callbacks.remove(callback)

    def _notify_callback(self, _bleak_uuid: str, data: Buf):
        # pylint: disable=protected-access
        if _bleak_uuid == self.uuid._bleak_uuid:
            for callback in self._notify_callbacks:
                callback(data)

    def __repr__(self) -> str:
        if self.uuid:
            return f"<Characteristic: {self.uuid}>"
        return "<Characteristic: uuid is None>"
