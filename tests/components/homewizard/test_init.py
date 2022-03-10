"""Tests for the homewizard component."""
from asyncio import TimeoutError
from unittest.mock import AsyncMock, patch

from homewizard_energy.errors import DisabledError

from homeassistant import config_entries
from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_load_unload(aioclient_mock, hass, mock_config_entry, init_integration):
    """Test loading and unloading of integration."""

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_load_failed_host_unavailable(
    aioclient_mock, hass, mock_config_entry, mock_homewizard_energy
):
    """Test setup handles unreachable host."""

    mock_config_entry.add_to_hass(hass)

    def MockInitialize():
        raise TimeoutError()

    mock_homewizard_energy.device.side_effect = MockInitialize

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=mock_homewizard_energy,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_failed_disabled(
    aioclient_mock, hass, mock_config_entry, mock_homewizard_energy
):
    """Test setup handles unreachable host."""

    mock_config_entry.add_to_hass(hass)

    def MockInitialize():
        raise DisabledError()

    mock_homewizard_energy.device.side_effect = MockInitialize

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=mock_homewizard_energy,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_init_accepts_and_migrates_old_entry(
    aioclient_mock, hass, mock_homewizard_energy
):
    """Test config flow accepts imported configuration."""

    # Add original entry
    original_entry = MockConfigEntry(
        domain="homewizard_energy",
        data={CONF_IP_ADDRESS: "1.2.3.4"},
        entry_id="old_id",
    )
    original_entry.add_to_hass(hass)

    # Give it some entities to see of they migrate properly
    ent_reg = er.async_get(hass)
    old_entity_active_power = ent_reg.async_get_or_create(
        "sensor",
        "homewizard_energy",
        "p1_active_power_unique_id",
        config_entry=original_entry,
        original_name="Active Power",
        suggested_object_id="p1_active_power",
    )
    old_entity_switch = ent_reg.async_get_or_create(
        "switch",
        "homewizard_energy",
        "socket_switch_unique_id",
        config_entry=original_entry,
        original_name="Switch",
        suggested_object_id="socket_switch",
    )
    old_entity_disabled_sensor = ent_reg.async_get_or_create(
        "sensor",
        "homewizard_energy",
        "socket_disabled_unique_id",
        config_entry=original_entry,
        original_name="Switch Disabled",
        suggested_object_id="socket_disabled",
        disabled_by=er.DISABLED_USER,
    )
    # Update some user-customs
    ent_reg.async_update_entity(old_entity_active_power.entity_id, name="new_name")
    ent_reg.async_update_entity(old_entity_switch.entity_id, icon="new_icon")

    imported_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4", "old_config_entry_id": "old_id"},
        source=config_entries.SOURCE_IMPORT,
        entry_id="new_id",
    )
    imported_entry.add_to_hass(hass)

    assert imported_entry.domain == DOMAIN
    assert imported_entry.domain != original_entry.domain

    # Add the entry_id to trigger migration
    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=mock_homewizard_energy,
    ):
        await hass.config_entries.async_setup(imported_entry.entry_id)
        await hass.async_block_till_done()

    assert original_entry.state is ConfigEntryState.NOT_LOADED
    assert imported_entry.state is ConfigEntryState.LOADED

    # Check if new entities are migrated
    new_entity_active_power = ent_reg.async_get(old_entity_active_power.entity_id)
    assert new_entity_active_power.platform == DOMAIN
    assert new_entity_active_power.name == "new_name"
    assert new_entity_active_power.icon is None
    assert new_entity_active_power.original_name == "Active Power"
    assert new_entity_active_power.unique_id == "p1_active_power_unique_id"
    assert new_entity_active_power.disabled_by is None

    new_entity_switch = ent_reg.async_get(old_entity_switch.entity_id)
    assert new_entity_switch.platform == DOMAIN
    assert new_entity_switch.name is None
    assert new_entity_switch.icon == "new_icon"
    assert new_entity_switch.original_name == "Switch"
    assert new_entity_switch.unique_id == "socket_switch_unique_id"
    assert new_entity_switch.disabled_by is None

    new_entity_disabled_sensor = ent_reg.async_get(old_entity_disabled_sensor.entity_id)
    assert new_entity_disabled_sensor.platform == DOMAIN
    assert new_entity_disabled_sensor.name is None
    assert new_entity_disabled_sensor.original_name == "Switch Disabled"
    assert new_entity_disabled_sensor.unique_id == "socket_disabled_unique_id"
    assert new_entity_disabled_sensor.disabled_by == er.DISABLED_USER


async def test_load_handles_generic_exception(
    aioclient_mock, hass, mock_homewizard_energy
):
    """Test setup catches generic exception."""

    def MockInitialize():
        raise DisabledError()

    mock_homewizard_energy.device = AsyncMock(side_effect=MockInitialize)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=mock_homewizard_energy,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
