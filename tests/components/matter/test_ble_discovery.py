"""Test parsing of Matter commissionable BLE advertisements."""

import pytest

from homeassistant.components.matter.ble_discovery import MatterBleAdvertisement

from .common import MATTER_BLE_SERVICE_DATA

ADVERTISEMENT = MatterBleAdvertisement(
    discriminator=3840, vendor_id=0xFFF1, product_id=0x8000
)
RAW_COMMISSIONABLE = bytes([0x0B, 0x16, 0xF6, 0xFF, *MATTER_BLE_SERVICE_DATA])
RAW_OTHER = bytes([0x02, 0x01, 0x06, 0x05, 0x16, 0xF0, 0xFF, 0x01, 0x02])


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(MATTER_BLE_SERVICE_DATA, ADVERTISEMENT, id="commissionable"),
        pytest.param(
            bytes([0x00, 0x34, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00]),
            MatterBleAdvertisement(discriminator=0x234, vendor_id=0, product_id=0),
            id="version_nibble_masked",
        ),
        pytest.param(
            bytes([0x01, *MATTER_BLE_SERVICE_DATA[1:]]), None, id="not_commissionable"
        ),
        pytest.param(MATTER_BLE_SERVICE_DATA[:7], None, id="short"),
        pytest.param(None, None, id="missing"),
    ],
)
def test_from_service_data(
    data: bytes | None, expected: MatterBleAdvertisement | None
) -> None:
    """Fields are unpacked little endian with a 12 bit discriminator."""
    assert MatterBleAdvertisement.from_service_data(data) == expected


def test_unique_id() -> None:
    """The unique id combines vendor, product and discriminator."""
    assert ADVERTISEMENT.unique_id == "fff18000f00"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(RAW_COMMISSIONABLE, ADVERTISEMENT, id="commissionable"),
        pytest.param(RAW_OTHER + RAW_COMMISSIONABLE, ADVERTISEMENT, id="after_other"),
        pytest.param(RAW_OTHER, None, id="other_service"),
        pytest.param(b"", None, id="empty"),
    ],
)
def test_from_raw(raw: bytes, expected: MatterBleAdvertisement | None) -> None:
    """Only the Matter service data in the packet itself counts."""
    assert MatterBleAdvertisement.from_raw(raw) == expected
