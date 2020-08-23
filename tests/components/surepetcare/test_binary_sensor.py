"""The tests for the surepetcare binary sensor platform."""
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import DOMAIN as BS_DOMAIN
from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.async_mock import patch

CONFIG = {
    DOMAIN: {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    },
}

HOUSEHOLD_ID = "household-id"


MOCK_API_DATA = {
}


async def test_unique_ids(hass) -> None:
    """Test the generation of unique ids."""
    with _patch_api_get_data(MOCK_API_DATA), _patch_sensor_setup():
        assert await async_setup_component(hass, DOMAIN, CONFIG)

    assert hass.states.get("binary_sensor.hub")
    assert hass.states.get("binary_sensor.connectivity")
    assert hass.states.get("binary_sensor.pet")


def _patch_api_get_data(return_value: Optional[Dict[str, Any]] = None):
    return patch(
        "homeassistant.components.surepetcare.SurePetcare.get_data",
        return_value=return_value,
    )


def _patch_sensor_setup():
    return patch(
        "homeassistant.components.surepetcare.sensor.async_setup_platform",
        return_value=True,
    )
