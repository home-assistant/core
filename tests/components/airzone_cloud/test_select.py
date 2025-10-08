"""The select tests for the Airzone Cloud platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.select import ATTR_OPTIONS, DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .util import async_init_integration


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_airzone_create_selects(hass: HomeAssistant) -> None:
    """Test creation of selects."""

    await async_init_integration(hass)

    # Zones
    state = hass.states.get("select.dormitorio_air_quality_mode")
    assert state.state == "auto"

    state = hass.states.get("select.dormitorio_mode")
    assert state is None

    state = hass.states.get("select.salon_air_quality_mode")
    assert state.state == "auto"

    state = hass.states.get("select.salon_mode")
    assert state.state == "cool"
    assert state.attributes.get(ATTR_OPTIONS) == [
        "cool",
        "dry",
        "fan",
        "heat",
    ]


async def test_airzone_select_air_quality_mode(hass: HomeAssistant) -> None:
    """Test select Air Quality mode."""

    await async_init_integration(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.dormitorio_air_quality_mode",
                ATTR_OPTION: "Invalid",
            },
            blocking=True,
        )

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.dormitorio_air_quality_mode",
                ATTR_OPTION: "off",
            },
            blocking=True,
        )

    state = hass.states.get("select.dormitorio_air_quality_mode")
    assert state.state == "off"


async def test_airzone_select_mode(hass: HomeAssistant) -> None:
    """Test select HVAC mode."""

    await async_init_integration(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.salon_mode",
                ATTR_OPTION: "Invalid",
            },
            blocking=True,
        )

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.salon_mode",
                ATTR_OPTION: "heat",
            },
            blocking=True,
        )

    state = hass.states.get("select.salon_mode")
    assert state.state == "heat"
