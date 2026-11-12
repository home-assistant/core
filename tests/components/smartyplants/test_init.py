"""Tests for the SmartyPlants integration setup."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pysmartyplants import (
    SmartyPlantsAuthError,
    SmartyPlantsConnectionError,
    SmartyPlantsError,
    SmartyPlantsForbiddenError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.smartyplants.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_added_entry, setup_integration


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads and unloads."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(SmartyPlantsConnectionError("boom"), id="connection"),
        pytest.param(SmartyPlantsForbiddenError("nope"), id="forbidden"),
    ],
)
async def test_setup_retries_when_first_poll_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smartyplants_client: AsyncMock,
    error: SmartyPlantsError,
) -> None:
    """Test setup is retried when the first poll fails."""
    mock_smartyplants_client.async_get_sensors.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


async def test_setup_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smartyplants_client: AsyncMock,
) -> None:
    """Test a rejected key during setup starts a reauth flow."""
    mock_smartyplants_client.async_get_sensors.side_effect = SmartyPlantsAuthError(
        "nope"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_poll_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smartyplants_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a key rejected on a scheduled poll starts a reauth flow."""
    await setup_integration(hass, mock_config_entry)
    assert not hass.config_entries.flow.async_progress()

    mock_smartyplants_client.async_get_sensors.side_effect = SmartyPlantsAuthError(
        "nope"
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_entry_without_webhook_polls(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an entry created without a webhook still loads and polls."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            key: value
            for key, value in mock_config_entry.data.items()
            if key != CONF_WEBHOOK_ID
        },
        unique_id=mock_config_entry.unique_id,
    )
    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_legacy_unique_id_is_migrated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an entity left by the custom integration keeps its entity id."""
    mock_config_entry.add_to_hass(hass)
    legacy = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "sensor-1_fertilise_days",
        config_entry=mock_config_entry,
        suggested_object_id="monstera_fertilise_in",
    )

    await setup_added_entry(hass, mock_config_entry)

    entry = entity_registry.async_get(legacy.entity_id)
    assert entry.unique_id == "sensor-1_fertilize"
    assert hass.states.get("sensor.monstera_fertilise_in").state == "21"


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_legacy_unique_id_kept_when_new_one_exists(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the old entry is left alone when the new id is already taken."""
    mock_config_entry.add_to_hass(hass)
    legacy = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "sensor-1_fertilise_days",
        config_entry=mock_config_entry,
        suggested_object_id="monstera_fertilise_in",
    )
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "sensor-1_fertilize",
        config_entry=mock_config_entry,
        suggested_object_id="monstera_fertilize_in",
    )

    await setup_added_entry(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        entity_registry.async_get(legacy.entity_id).unique_id
        == "sensor-1_fertilise_days"
    )
