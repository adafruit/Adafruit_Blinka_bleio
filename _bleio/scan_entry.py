# SPDX-FileCopyrightText: Copyright (c) 2020 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`_bleio.scan_entry`
=======================================================================

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional, Union

from bleak.backends.device import BLEDevice

from .address import Address
from .uuid_ import UUID

Buf = Union[bytes, bytearray, memoryview]
DataDict = Dict[int, Buf]


class ScanEntry:
    # Some device names are created by the bleak code or what it calls, and aren't the
    # real advertised name. Suppress those. Patterns seen include (XX are hex digits):
    # dev_XX_XX_XX_XX_XX_XX
    # XX-XX-XX-XX-XX-XX
    # Unknown
    _RE_IGNORABLE_NAME = re.compile(
        r"((dev_)?"
        r"[0-9A-F]{2}[-_][0-9A-F]{2}[-_][0-9A-F]{2}[-_][0-9A-F]{2}[-_][0-9A-F]{2}[-_][0-9A-F]{2})"
        r"|Unknown",
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        address: Address,
        rssi: int,
        advertisement_bytes: Optional[Buf] = None,
        connectable: bool,
        scan_response: bool,
        data_dict: Optional[DataDict] = None,
    ):
        """Should not be instantiated directly. Use `_bleio.Adapter.start_scan`."""
        self._address = address
        self._rssi = rssi
        self._advertisement_bytes = advertisement_bytes
        self._connectable = connectable
        self._scan_response = scan_response
        self._data_dict = data_dict
        if advertisement_bytes and data_dict:
            raise ValueError(
                "advertisement_bytes and data_dict must not both be supplied"
            )

    @classmethod
    def _from_bleak(cls, device: BLEDevice) -> "ScanEntry":
        return cls(
            address=Address(string=device.address),
            rssi=device.rssi,
            # connectable is a guess, based on UUIDS being advertised or not.
            connectable="uuids" in device.metadata,
            scan_response=False,
            data_dict=cls._data_dict_from_bleak(device),
        )

    def matches(
        self,
        prefixes: bytes,
        match_all: bool = True,
    ) -> bool:
        # We may not have the original advertisement bytes, so we can't
        # do a perfect job of matching.
        if len(prefixes) == 0:
            return True
        fields = self._advertisement_fields
        for prefix in self._separate_prefixes(prefixes):
            prefix_matched = False
            for field in fields:
                if field.startswith(prefix):
                    if not match_all:
                        return True
                    prefix_matched = True
                    break
            # if all, this prefix must match at least one field
            if not prefix_matched and match_all:
                return False

        # All prefixes matched some field (if all), or none did (if any).
        return match_all

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"<ScanEntry {str(self._address)}>"

    @property
    def address(self) -> Address:
        return self._address

    @property
    def rssi(self) -> int:
        return self._rssi

    @property
    def connectable(self) -> bool:
        return self._connectable

    @property
    def scan_response(self) -> bool:
        return self._scan_response

    @property
    def advertisement_bytes(self) -> bytes:
        """The original advertisement bytes may not be available. Concatenate the
        data_dict entries to make an incomplete advertising bytestring.
        """
        if self._advertisement_bytes:
            return self._advertisement_bytes
        return b"".join(
            bytes((len(field),)) + field for field in self._advertisement_fields
        )

    @property
    def _advertisement_fields(self) -> List[bytes]:
        """The individual data fields of the advertisement, without length headers.
        Each field is one byte of advertising data type followed by the data.
        """
        if self._advertisement_bytes is not None:
            fields = []
            idx = 0
            while idx < len(self._advertisement_bytes):
                field_length = self._advertisement_bytes[idx]
                idx += 1
                fields.append(self._advertisement_bytes[idx : idx + field_length])
                idx += field_length
            return fields

        return tuple(
            bytes((data_type,)) + data for data_type, data in self._data_dict.items()
        )

    @staticmethod
    def _data_dict_from_bleak(device: BLEDevice) -> DataDict:
        data_dict = {}
        for key, value in device.metadata.items():
            if key == "manufacturer_data":
                # The manufacturer data value is a dictionary.
                # Re-concatenate it into bytes
                all_mfr_data = bytearray()
                for mfr_id, mfr_data in value.items():
                    all_mfr_data.extend(mfr_id.to_bytes(2, byteorder="little"))
                    all_mfr_data.extend(mfr_data)
                data_dict[0xFF] = all_mfr_data
            elif key == "uuids":
                uuids16 = bytearray()
                uuids128 = bytearray()
                for uuid in value:
                    bleio_uuid = UUID(uuid)
                    # If this is a Standard UUID in 128-bit form, convert it to a 16-bit UUID.
                    if bleio_uuid.is_standard_uuid:
                        uuids16.extend(bleio_uuid.uuid128[12:14])
                    else:
                        uuids128.extend(bleio_uuid.uuid128)

            if uuids16:
                # Complete list of 16-bit UUIDs.
                data_dict[0x03] = uuids16
            if uuids128:
                # Complete list of 128-bit UUIDs
                data_dict[0x07] = uuids128

        if not ScanEntry._RE_IGNORABLE_NAME.fullmatch(device.name):
            # Complete name
            data_dict[0x09] = device.name.encode("utf-8")

        return data_dict

    @staticmethod
    def _separate_prefixes(prefixes_bytes: bytes) -> List[bytes]:
        """Separate a concatenated prefix bytestring into separate prefix strings."""
        i = 0
        prefixes = []
        while i < len(prefixes_bytes):
            length = prefixes_bytes[i]
            i += 1
            prefixes.append(prefixes_bytes[i : i + length])
            i += length

        return prefixes
