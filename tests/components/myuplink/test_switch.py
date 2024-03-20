"""Tests for myuplink switch module."""

from unittest.mock import MagicMock

from aiohttp import ClientError
import pytest

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

TEST_PLATFORM = Platform.SWITCH
pytestmark = pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)])

ENTITY_ID = "switch.gotham_city_temporary_lux"
ENTITY_FRIENDLY_NAME = "Gotham City Tempo\xadrary lux"
ENTITY_UID = "robin-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff-50004"


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
    """Test the switch attributes are correct."""

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes == {
        "friendly_name": ENTITY_FRIENDLY_NAME,
    }


@pytest.mark.parametrize(
    ("service"),
    [
        (SERVICE_TURN_ON),
        (SERVICE_TURN_OFF),
    ],
)
async def test_switching(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
    service: str,
) -> None:
    """Test the switch can be turned on/off."""

    await hass.services.async_call(
        TEST_PLATFORM, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()
    mock_myuplink_client.async_set_device_points.assert_called_once()


@pytest.mark.parametrize(
    ("service"),
    [
        (SERVICE_TURN_ON),
        (SERVICE_TURN_OFF),
    ],
)
async def test_api_failure(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
    service: str,
) -> None:
    """Test handling of exception from API."""

    with pytest.raises(HomeAssistantError):
        mock_myuplink_client.async_set_device_points.side_effect = ClientError
        await hass.services.async_call(
            TEST_PLATFORM, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
        await hass.async_block_till_done()
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

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == ENTITY_UID
