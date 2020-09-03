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
`_bleio.connection`
=======================================================================

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""
from __future__ import annotations
from typing import Iterable, Tuple, Union

from bleak import BleakClient

import _bleio.adapter_ as adap
import _bleio.address
import _bleio.service


Buf = Union[bytes, bytearray, memoryview]

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"


class Connection:
    """A BLE connection to another device. Used to discover and interact with services on the other
    device.

    Usage::

       import _bleio

       my_entry = None
       for entry in adapter.scan(2.5):
           if entry.name is not None and entry.name == 'InterestingPeripheral':
               my_entry = entry
               break

       if not my_entry:
           raise Exception("'InterestingPeripheral' not found")

       connection = adapter.connect(my_entry.address, timeout=10)"""

    def __init__(self, address: _bleio.address.Address):
        """Connections should not be created directly.
        Instead, to initiate a connection use `_bleio.Adapter.connect`.
        Connections may also be made when another device initiates a connection. To use a Connection
        created by a peer, read the `_bleio.Adapter.connections` property.

        :param _bleio.address.Address address: _bleio.address.Address of device to connect to
        """
        self._address = address
        self.__bleak_client = None

    @classmethod
    def _from_bleak(
        cls, address: _bleio.address.Address, _bleak_client: BleakClient
    ) -> "Connection":
        """Create a Connection from bleak information.

        :param ~_bleio.address.Address address: Address of device to connect to
        :param BleakClient _bleak_client: BleakClient used to make connection. (Blinka _bleio only)
        """
        conn = Connection(address)
        conn.__bleak_client = _bleak_client  # pylint: disable=protected-access
        return conn

    @property
    def _bleak_client(self):
        return self.__bleak_client

    def disconnect(self) -> None:
        """Disconnects from the remote peripheral. Does nothing if already disconnected."""
        adap.adapter.delete_connection(self)
        adap.adapter.await_bleak(self._disconnect_async())

    async def _disconnect_async(self) -> None:
        """Disconnects from the remote peripheral. Does nothing if already disconnected."""
        await self.__bleak_client.disconnect()

    def pair(self, *, bond: bool = True) -> None:
        """Pair to the peer to improve security."""
        raise NotImplementedError("Pairing not implemented")

    def discover_remote_services(
        self, service_uuids_whitelist: Iterable = None
    ) -> Tuple[_bleio.service.Service]:
        return adap.adapter.await_bleak(
            self._discover_remote_services_async(service_uuids_whitelist)
        )

    async def _discover_remote_services_async(
        self, service_uuids_whitelist: Iterable = None
    ) -> Tuple[_bleio.service.Service]:
        """Do BLE discovery for all services or for the given service UUIDS,
         to find their handles and characteristics, and return the discovered services.
         `Connection.connected` must be True.

        :param iterable service_uuids_whitelist:

          an iterable of :py:class:~`UUID` objects for the services provided by the peripheral
          that you want to use.

          The peripheral may provide more services, but services not listed are ignored
          and will not be returned.

          If service_uuids_whitelist is None, then all services will undergo discovery, which can be
          slow.

          If the service UUID is 128-bit, or its characteristic UUID's are 128-bit, you
          you must have already created a :py:class:~`UUID` object for that UUID in order for the
          service or characteristic to be discovered. Creating the UUID causes the UUID to be
          registered for use. (This restriction may be lifted in the future.)

        :return: A tuple of `_bleio.Service` objects provided by the remote peripheral."""
        _bleak_service_uuids_whitelist = ()
        if service_uuids_whitelist:
            _bleak_service_uuids_whitelist = tuple(
                # pylint: disable=protected-access
                uuid._bleak_uuid
                for uuid in service_uuids_whitelist
            )

        _bleak_services = await self.__bleak_client.get_services()
        # pylint: disable=protected-access
        return tuple(
            _bleio.service.Service._from_bleak(self, _bleak_service)
            for _bleak_service in _bleak_services
            if _bleak_service.uuid.lower() in _bleak_service_uuids_whitelist
        )

    @property
    def connected(self) -> bool:
        """True if connected to the remote peer."""
        return adap.adapter.await_bleak(self.__bleak_client.is_connected())

    @property
    def paired(self) -> bool:
        """True if paired to the remote peer."""
        raise NotImplementedError("Pairing not implemented")

    @property
    def connection_interval(self) -> float:
        """Time between transmissions in milliseconds. Will be multiple of 1.25ms. Lower numbers
        increase speed and decrease latency but increase power consumption.

        When setting connection_interval, the peer may reject the new interval and
        `connection_interval` will then remain the same.

        Apple has additional guidelines that dictate should be a multiple of 15ms except if HID is
        available. When HID is available Apple devices may accept 11.25ms intervals."""
        raise NotImplementedError()

    @connection_interval.setter
    def connection_interval(self, value: float) -> None:
        raise NotImplementedError()

    @property
    def max_packet_length(self) -> int:
        """The maximum number of data bytes that can be sent in a single transmission,
        not including overhead bytes.

        This is the maximum number of bytes that can be sent in a notification,
        which must be sent in a single packet.
        But for a regular characteristic read or write, may be sent in multiple packets,
        so this limit does not apply."""
        raise NotImplementedError("max_packet_length not available")

    def __repr__(self):
        return "<Connection: {}".format(self._address)
