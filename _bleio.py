# The MIT License (MIT)
#
# Copyright (c) 2020 Scott Shawcroft for Adafruit Industries LLC
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
`adafruit_blinka_bleio`
================================================================================

`_bleio` for Blinka based on `bleak`


* Author(s): Scott Shawcroft

"""

import asyncio
import bleak
import struct
import time

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"

from adafruit_ble import advertising

class Address:
    def __init__(self, address):
        if isinstance(address, bytes):
            self.address_bytes = address
        elif isinstance(address, str):
            address = address.split(":")
            self.address_bytes = bytes([int(x, 16) for x in address])

class ScanEntry:
    def __init__(self, bleak_device):
        self.rssi = bleak_device.rssi
        self._data_dict = {}
        if "manufacturer_data" in bleak_device.metadata:
            mfg_data = bleak_device.metadata["manufacturer_data"]
            self._data_dict[0xff] = []
            for mfg in mfg_data:
                self._data_dict[0xff].append(struct.pack("<H", mfg) + bytes(mfg_data[mfg]))
        #print(self._data_dict)
        self.address = Address(bleak_device.address)

        self.advertisement_bytes = advertising.encode_data(self._data_dict)
        #print(bleak_device.address, bleak_device.name, bleak_device.metadata)

        self.connectable = bool(bleak_device.metadata["uuids"])
        self.scan_response = False

    def matches(self, prefixes, *, all=True):
        i = 0
        while i < len(prefixes):
            prefix_len = prefixes[i]
            i += 1
            adt = prefixes[i]
            if adt in self._data_dict:
                field = self._data_dict[adt]
                if not isinstance(field, list):
                    field = [field]
                found = False
                for value in field:
                    if value.startswith(prefixes[i+1:i+prefix_len-1]):
                        found = True
                        break

                if not all and found:
                    print("matches", prefixes, self._data_dict, self.advertisement_bytes)
                    return True
                elif all and not found:
                    return False
            elif all:
                return False
            i += prefix_len
        if all:
            print("matches", prefixes, self._data_dict, self.advertisement_bytes)
        return all

class Adapter:
    def __init__(self, address):
        self.address = Address(address)

    def start_scan(self, prefixes=b"", *, buffer_size=512, extended=False, timeout=0.1, interval=0.1, window=None, minimum_rssi=-80, active=True):
        start_time = time.monotonic()
        while not timeout or time.monotonic() - start_time < timeout:
            devices = asyncio.get_event_loop().run_until_complete(bleak.discover(timeout=interval))
            for device in devices:
                se = ScanEntry(device)
                if se.matches(prefixes, all=False):
                    yield se

    def stop_scan(self):
        pass

class Attribute:
    NO_ACCESS = 0
    OPEN = 0
    ENCRYPT_NO_MITM = 0
    ENCRYPT_WITH_MITM = 0
    LESC_ENCRYPT_WITH_MITM = 0
    SIGNED_NO_MITM = 0
    SIGNED_WITH_MITM = 0

class UUID:
    def __init__(self, uuid):
        # Stub out UUID
        self.size = 128
        self.uuid128 = b"\x00" * (128 // 8)

class Descriptor:
    @staticmethod
    def add_to_characteristic(characteristic, uuid, *, read_perm=Attribute.OPEN,
                              write_perm=Attribute.OPEN, max_length=20, fixed_length=False,
                              initial_value=b''):
        pass

class CharacteristicBuffer:
    pass

class PacketBuffer:
    pass

class Characteristic:
    BROADCAST = 0
    READ = 0
    WRITE = 0
    NOTIFY = 0
    INDICATE = 0
    WRITE_NO_RESPONSE = 0

    @staticmethod
    def add_to_service(service, uuid, *, properties=0, read_perm=Attribute.OPEN,
                       write_perm=Attribute.OPEN, max_length=20, fixed_length=False,
                       initial_value=None):
        raise NotImplementedError()

adapter = Adapter(b"\x00\x00\x00\x00\x00\x00")
