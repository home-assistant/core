"""Common fixtures for the fever_smart tests."""
import logging

from homeassistant.components.fever_smart.fever_smart import FeverSmartAdvParser

_LOGGER = logging.getLogger(__name__)


def test_fever_smart() -> None:
    result = FeverSmartAdvParser.process(
        "0201040303091817ff0720356e6235cd9e13c19f1eb7f8c6fa9de6bef09b44", "0m0d3s2c"
    )

    assert result["temp"] == 18.9375
    assert result["device_id"] == "C50/00013678"
