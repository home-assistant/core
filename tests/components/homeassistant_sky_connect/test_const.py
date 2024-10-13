"""Test the Home Assistant SkyConnect constants."""

import pytest

from homeassistant.components.homeassistant_sky_connect.const import HardwareVariant


@pytest.mark.parametrize(
    ("usb_product_name", "expected_variant"),
    [
        ("SkyConnect v1.0", HardwareVariant.SKYCONNECT),
        ("Home Assistant Connect ZBT-1", HardwareVariant.CONNECT_ZBT1),
    ],
)
def test_hardware_variant(
    usb_product_name: str, expected_variant: HardwareVariant
) -> None:
    """Test hardware variant parsing."""
    assert HardwareVariant.from_usb_product_name(usb_product_name) == expected_variant


def test_hardware_variant_invalid() -> None:
    """Test hardware variant parsing with an invalid product."""
    with pytest.raises(
        ValueError, match=r"^Unknown SkyConnect product name: Some other product$"
    ):
        HardwareVariant.from_usb_product_name("Some other product")
