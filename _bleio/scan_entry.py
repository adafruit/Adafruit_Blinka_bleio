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

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""

from _bleio import Address, UUID


class ScanEntry:
    def __init__(self, device):
        # TODO break down device
        self._device = device
        self._address = Address(string=device.address)
        self._data_dict = self._build_data_dict()

    def matches(self, prefixes, any_: bool = True) -> bool:
        # We don't have the original advertisement bytes, so we can't
        # do a perfect job of matching.
        if len(prefixes) == 0:
            return True
        fields = self.advertisement_fields
        for prefix in self._separate_prefixes(prefixes):
            prefix_matched = False
            for field in fields:
                if field.startswith(prefix):
                    if any_:
                        return True
                    prefix_matched = True
            if not prefix_matched:
                return False

        # All prefixes matched some field.
        return True

    def __repr__(self):
        return str(self)

    def __str__(self):
        return str(self._device)

    @property
    def address(self):
        return self._address

    @property
    def rssi(self):
        return self._device.rssi

    @property
    def connectable(self):
        """This is unknown on most Blinka implementations. Always returns ``None``."""
        return None

    @property
    def scan_response(self):
        """The original scan response is not available. Always returns ``None``."""
        return None

    @property
    def advertisement_bytes(self):
        """The original advertisement bytes are not available. Concatenate the
        data_dict entries to make an incomplete advertising bytestring.
        """
        return b"".join(
            bytes((len(field),)) + field for field in self.advertisement_fields
        )

    @property
    def advertisement_fields(self):
        """The individual data fields of the advertisement, without length headers.
        Each field is one byte of advertising data type followed by the data.
        """
        return tuple(
            bytes((data_type,)) + data for data_type, data in self.data_dict.items()
        )

    @property
    def data_dict(self):
        """Return the parsed advertisement dictionary. Each key is an advertising
        data type value. This can substitute for the data that is passed
        in `advertisement_bytes`.
        """
        return self._data_dict

    def _build_data_dict(self):
        data = {}
        for key, value in self._device.metadata.items():
            if key == "manufacturer_data":
                data[0xFF] = value
            elif key == "uuids":
                uuids16 = bytearray()
                uuids128 = bytearray()
                for uuid in value:
                    bleio_uuid = UUID(uuid)
                    # If this is a Standard UUID in 128-bit form, convert it to a 16-bit UUID.
                    if bleio_uuid.is_standard_uuid:
                        uuids16.extend(bleio_uuid.uuid128[12:13])
                    else:
                        uuids128.extend(bleio_uuid.uuid128)

            if uuids16:
                # Complete list of 16-bit UUIDs.
                data[0x03] = uuids16
            if uuids128:
                # Complete list of 128-bit UUIDs
                data[0x07] = uuids128

        return data

    @staticmethod
    def _separate_prefixes(prefixes_bytes):
        """Separate a concatenated prefix bytestring into separate prefix strings."""
        i = 0
        prefixes = []
        while i < len(prefixes_bytes):
            length = prefixes_bytes[i]
            prefixes.append(prefixes_bytes[i + 1 : i + length])
            i += length + 1
