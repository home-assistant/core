"""Tests for Ecobulles device metadata helpers."""

from homeassistant.components.ecobulles.device import (
    mac_from_eco_ref,
    model_from_serial_number,
)


def test_model_from_serial_number() -> None:
    """Infer known model names from observed serial prefixes."""
    assert model_from_serial_number("XC240007") == "Ecobulles Expert"
    assert model_from_serial_number("E123456") == "Ecobulles Équilibre"
    assert model_from_serial_number("Z123456") == "Ecobulles"
    assert model_from_serial_number(None) == "Ecobulles"


def test_mac_from_eco_ref() -> None:
    """Only MAC-shaped Ecobulles references become device-registry connections."""
    assert mac_from_eco_ref("44B7D095E9C6") == "44:b7:d0:95:e9:c6"
    assert mac_from_eco_ref("44:B7:D0:95:E9:C6") == "44:b7:d0:95:e9:c6"
    assert mac_from_eco_ref("not-a-mac") is None
