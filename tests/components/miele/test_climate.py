"""Tests for miele climate module."""

from unittest.mock import MagicMock

from aiohttp import ClientError
from pymiele import MieleDevices
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.miele.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import get_actions_callback, get_data_callback

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform

TEST_PLATFORM = CLIMATE_DOMAIN
pytestmark = [
    pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)]),
    pytest.mark.parametrize(
        "load_action_file",
        ["action_freezer.json"],
        ids=[
            "freezer",
        ],
    ),
]

ENTITY_ID = "climate.freezer"
SERVICE_SET_TEMPERATURE = "set_temperature"


async def test_climate_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test climate entity state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_states_api_push(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
    device_fixture: MieleDevices,
) -> None:
    """Test climate state when the API pushes data via SSE."""

    data_callback = get_data_callback(mock_miele_client)
    await data_callback(device_fixture)
    await hass.async_block_till_done()

    act_file = load_json_object_fixture("4_actions.json", DOMAIN)
    action_callback = get_actions_callback(mock_miele_client)
    await action_callback(act_file)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


async def test_set_target(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
) -> None:
    """Test the climate can be turned on/off."""

    await hass.services.async_call(
        TEST_PLATFORM,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: -17},
        blocking=True,
    )
    mock_miele_client.set_target_temperature.assert_called_once_with(
        "Dummy_Appliance_1", -17.0, 1
    )


async def test_api_failure(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
) -> None:
    """Test handling of exception from API."""
    mock_miele_client.set_target_temperature.side_effect = ClientError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TEST_PLATFORM,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: -17},
            blocking=True,
        )
    mock_miele_client.set_target_temperature.assert_called_once()
