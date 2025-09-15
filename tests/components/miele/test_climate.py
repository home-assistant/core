"""Tests for miele climate module."""

from unittest.mock import MagicMock

from aiohttp import ClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

TEST_PLATFORM = CLIMATE_DOMAIN
pytestmark = pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)])

ENTITY_ID = "climate.freezer"
SERVICE_SET_TEMPERATURE = "set_temperature"


@pytest.mark.parametrize("load_action_file", ["action_freezer.json"], ids=["freezer"])
async def test_climate_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test climate entity state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["fridge_freezer.json"])
@pytest.mark.parametrize(
    "load_action_file", ["action_offline.json"], ids=["fridge_freezer_offline"]
)
async def test_climate_states_offline(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test climate entity state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["fridge_freezer.json"])
@pytest.mark.parametrize(
    "load_action_file", ["action_fridge_freezer.json"], ids=["fridge_freezer"]
)
async def test_climate_states_mulizone(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test climate entity state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("load_action_file", ["action_freezer.json"], ids=["freezer"])
async def test_climate_states_api_push(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
    push_data_and_actions: None,
) -> None:
    """Test climate state when the API pushes data via SSE."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_action_file", ["action_freezer.json"], ids=["freezer"])
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


@pytest.mark.parametrize("load_action_file", ["action_freezer.json"], ids=["freezer"])
async def test_api_failure(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
) -> None:
    """Test handling of exception from API."""
    mock_miele_client.set_target_temperature.side_effect = ClientError

    with pytest.raises(
        HomeAssistantError, match=f"Failed to set state for {ENTITY_ID}"
    ):
        await hass.services.async_call(
            TEST_PLATFORM,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: -17},
            blocking=True,
        )
    mock_miele_client.set_target_temperature.assert_called_once()
