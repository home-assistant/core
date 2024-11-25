"""Tests for myuplink switch module."""

from unittest.mock import MagicMock

from aiohttp import ClientError
import pytest

from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

TEST_PLATFORM = Platform.NUMBER
pytestmark = pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)])

ENTITY_ID = "number.gotham_city_heating_offset_climate_system_1"
ENTITY_FRIENDLY_NAME = "Gotham City Heating offset climate system 1"
ENTITY_UID = "robin-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff-47011"


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test that the entities are registered in the entity registry."""

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == ENTITY_UID


async def test_attributes(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test the entity attributes are correct."""

    state = hass.states.get(ENTITY_ID)
    assert state.state == "1.0"
    assert state.attributes == {
        "friendly_name": ENTITY_FRIENDLY_NAME,
        "min": -10.0,
        "max": 10.0,
        "mode": "auto",
        "step": 1.0,
    }


async def test_set_value(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test the value of the number entity can be set."""

    await hass.services.async_call(
        TEST_PLATFORM,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_ID, "value": 1},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_myuplink_client.async_set_device_points.assert_called_once()


async def test_api_failure(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test handling of exception from API."""

    mock_myuplink_client.async_set_device_points.side_effect = ClientError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TEST_PLATFORM,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_ID, "value": 1},
            blocking=True,
        )
    mock_myuplink_client.async_set_device_points.assert_called_once()


@pytest.mark.parametrize(
    "load_device_points_file",
    ["device_points_nibe_smo20.json"],
)
async def test_entity_registry_smo20(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test that the entities are registered in the entity registry."""

    entry = entity_registry.async_get("number.gotham_city_change_in_curve")
    assert entry.unique_id == "robin-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff-47028"
