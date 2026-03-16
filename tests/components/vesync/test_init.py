"""Tests for the init module."""

from unittest.mock import AsyncMock, patch

import pytest
from pyvesync import VeSync
from pyvesync.utils.errors import (
    VeSyncAPIResponseError,
    VeSyncLoginError,
    VeSyncServerError,
)

from homeassistant.components.vesync import (
    async_remove_config_entry_device,
    async_setup_entry,
)
from homeassistant.components.vesync.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (VeSyncLoginError("Mock login failed"), ConfigEntryState.SETUP_ERROR),
        (VeSyncAPIResponseError("Mock login failed"), ConfigEntryState.SETUP_RETRY),
        (VeSyncServerError("Mock login failed"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_async_setup_entry_login_errors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup handles different login errors appropriately."""
    manager.login = AsyncMock(side_effect=exception)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert manager.login.call_count == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is expected_state


async def test_async_setup_entry__no_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync
) -> None:
    """Test setup connects to vesync and creates empty config when no devices."""
    with patch.object(hass.config_entries, "async_forward_entry_setups") as setups_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert setups_mock.call_args.args[1] == [
            Platform.BINARY_SENSOR,
            Platform.FAN,
            Platform.HUMIDIFIER,
            Platform.LIGHT,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SWITCH,
            Platform.UPDATE,
        ]

    assert manager.login.call_count == 1


async def test_async_setup_entry__loads_fans(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync, fan
) -> None:
    """Test setup connects to vesync and loads fan."""
    manager._dev_list["fans"].append(fan)

    with patch.object(hass.config_entries, "async_forward_entry_setups") as setups_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert setups_mock.call_args.args[1] == [
            Platform.BINARY_SENSOR,
            Platform.FAN,
            Platform.HUMIDIFIER,
            Platform.LIGHT,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SWITCH,
            Platform.UPDATE,
        ]
    assert manager.login.call_count == 1


async def test_migrate_config_entry(
    hass: HomeAssistant,
    switch_old_id_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration of config entry. Only migrates switches to a new unique_id."""
    switch: er.RegistryEntry = entity_registry.async_get_or_create(
        domain="switch",
        platform="vesync",
        unique_id="switch",
        config_entry=switch_old_id_config_entry,
        suggested_object_id="switch",
    )

    humidifier: er.RegistryEntry = entity_registry.async_get_or_create(
        domain="humidifier",
        platform="vesync",
        unique_id="humidifier",
        config_entry=switch_old_id_config_entry,
        suggested_object_id="humidifier",
    )

    assert switch.unique_id == "switch"
    assert switch_old_id_config_entry.minor_version == 1
    assert humidifier.unique_id == "humidifier"

    await hass.config_entries.async_setup(switch_old_id_config_entry.entry_id)
    await hass.async_block_till_done()

    assert switch_old_id_config_entry.minor_version == 3

    migrated_switch = entity_registry.async_get(switch.entity_id)
    assert migrated_switch is not None
    assert migrated_switch.entity_id.startswith("switch")
    assert migrated_switch.unique_id == "switch-device_status"
    # Confirm humidifier was not impacted
    migrated_humidifier = entity_registry.async_get(humidifier.entity_id)
    assert migrated_humidifier is not None
    assert migrated_humidifier.unique_id == "humidifier"

    # Assert that entity exists in the switch domain
    switch_entities = [
        e for e in entity_registry.entities.values() if e.domain == "switch"
    ]
    assert len(switch_entities) == 3

    humidifier_entities = [
        e for e in entity_registry.entities.values() if e.domain == "humidifier"
    ]
    assert len(humidifier_entities) == 2
    assert switch_old_id_config_entry.version == 1
    assert switch_old_id_config_entry.unique_id == "TESTACCOUNTID"


async def test_async_remove_config_entry_device_positive(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: ConfigEntry,
    manager: VeSync,
    fan,
) -> None:
    """Test removing a config entry from a device when no match is found."""

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    manager._dev_list["fans"].append(fan)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "test_device")},
    )

    result = await async_remove_config_entry_device(hass, config_entry, device_entry)

    assert result is True


async def test_async_remove_config_entry_device_negative(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: ConfigEntry,
    manager: VeSync,
    fan,
) -> None:
    """Test removing a config entry from a device when a match is found."""

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    manager._dev_list["fans"].append(fan)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "fan")},
    )

    # Call the remove method
    result = await async_remove_config_entry_device(hass, config_entry, device_entry)

    # Assert it returns False (device matched)
    assert result is False
