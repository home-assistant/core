"""Tests for the EnergyID sensor platform."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory  # Import the type hint
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.energyid.const import (
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_ID,
    DOMAIN,
)
from homeassistant.components.energyid.sensor import (
    async_setup_entry as sensor_async_setup_entry,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    MOCK_CONFIG_DATA,
    MOCK_OPTIONS_DATA,
    TEST_DEVICE_ID,
    TEST_RECORD_NAME,
)

from tests.common import MockConfigEntry


async def test_status_sensor_setup_and_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the setup of the status sensor and its attributes."""
    fixed_time = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
    freezer.move_to(fixed_time)
    mock_webhook_client.last_sync_time = fixed_time
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_status"
    )
    assert entity_id is not None
    entry = ent_reg.async_get(entity_id)

    assert entry is not None
    assert entry.unique_id == f"{mock_config_entry.entry_id}_status"
    assert entry.config_entry_id == mock_config_entry.entry_id
    assert entry.original_name == "Status"
    assert entry.entity_category == "diagnostic"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == str(len(MOCK_OPTIONS_DATA))
    attributes = dict(state.attributes)
    attributes["last_sync"] = fixed_time.isoformat() if fixed_time else None
    attributes["mapped_entities"] = dict(
        sorted(attributes.get("mapped_entities", {}).items())
    )
    assert attributes == snapshot


async def test_status_sensor_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test the device information for the status sensor."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    dev_reg = dr.async_get(hass)
    device_entry = dev_reg.async_get_device(identifiers={(DOMAIN, TEST_DEVICE_ID)})

    assert device_entry is not None
    assert device_entry.name == TEST_RECORD_NAME
    assert device_entry.manufacturer == "EnergyID"
    assert device_entry.model == "Webhook Bridge"
    assert device_entry.entry_type == "service"
    assert device_entry.config_entries == {mock_config_entry.entry_id}


async def test_status_sensor_updates_on_config_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the status sensor updates when config entry options change."""
    fixed_time = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
    freezer.move_to(fixed_time)
    mock_webhook_client.last_sync_time = fixed_time
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_status"
    )
    assert entity_id is not None

    state_before = hass.states.get(entity_id)
    assert state_before.state == "1"

    new_options = mock_config_entry.options.copy()
    new_options["sensor.another_energy"] = {
        CONF_HA_ENTITY_ID: "sensor.another_energy",
        CONF_ENERGYID_KEY: "gas",
    }
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)
    await hass.async_block_till_done()

    state_after = hass.states.get(entity_id)
    assert state_after is not None
    assert state_after.state == "2"
    attributes_after = dict(state_after.attributes)
    attributes_after["last_sync"] = fixed_time.isoformat() if fixed_time else None
    attributes_after["mapped_entities"] = dict(
        sorted(attributes_after["mapped_entities"].items())
    )
    assert attributes_after == snapshot(name="attributes_after_options_update")


async def test_status_sensor_handles_missing_client_data(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,  # Add freezer
) -> None:
    """Test sensor handles missing client or partial data gracefully."""
    fixed_time = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
    freezer.move_to(fixed_time)  # Freeze time for consistent 'now' if used

    entry_missing_data = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        options={},
        entry_id="test_entry_missing_client",
        title=TEST_RECORD_NAME,
    )
    entry_missing_data.add_to_hass(hass)

    with patch(
        "homeassistant.components.energyid.WebhookClient", return_value=MagicMock()
    ) as mock_client_init:
        client_instance = mock_client_init.return_value
        client_instance.is_claimed = None
        client_instance.last_sync_time = None
        client_instance.webhook_url = None
        client_instance.webhook_policy = None
        client_instance.authenticate = AsyncMock(return_value=True)
        client_instance.close = AsyncMock()
        client_instance.start_auto_sync = MagicMock()
        client_instance.get_or_create_sensor = MagicMock()
        client_instance.device_name = TEST_RECORD_NAME

        assert await hass.config_entries.async_setup(entry_missing_data.entry_id)
        await hass.async_block_till_done()

    assert entry_missing_data.state == ConfigEntryState.LOADED

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{entry_missing_data.entry_id}_status"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"
    attributes = dict(state.attributes)
    attributes["last_sync"] = None
    attributes["claimed"] = None
    attributes["webhook_endpoint"] = None
    attributes["webhook_policy"] = None
    attributes["mapped_entities"] = dict(
        sorted(attributes.get("mapped_entities", {}).items())
    )
    assert attributes == snapshot


async def test_status_sensor_setup_with_no_domain_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sensor setup logs error if main domain data is missing."""
    mock_config_entry.add_to_hass(hass)

    if DOMAIN in hass.data:
        del hass.data[DOMAIN]

    mock_add_entities = MagicMock()
    await sensor_async_setup_entry(hass, mock_config_entry, mock_add_entities)
    await hass.async_block_till_done()

    assert (
        f"EnergyID data not found for entry {mock_config_entry.entry_id} during sensor setup"
        in caplog.text
    )
    mock_add_entities.assert_not_called()
