"""Tests for the init module."""

from unittest.mock import Mock, patch

import pytest
from pyvesync import VeSync

from homeassistant.components.vesync import SERVICE_UPDATE_DEVS, async_setup_entry
from homeassistant.components.vesync.const import DOMAIN, VS_DEVICES, VS_MANAGER
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_async_setup_entry__not_login(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup does not create config entry when not logged in."""
    manager.login = Mock(return_value=False)

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as setups_mock,
        patch(
            "homeassistant.components.vesync.async_generate_device_list"
        ) as process_mock,
    ):
        assert not await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()
        assert setups_mock.call_count == 0
        assert process_mock.call_count == 0

    assert manager.login.call_count == 1
    assert DOMAIN not in hass.data
    assert "Unable to login to the VeSync server" in caplog.text


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
        ]

    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert not hass.data[DOMAIN][VS_DEVICES]


async def test_async_setup_entry__loads_fans(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync, fan
) -> None:
    """Test setup connects to vesync and loads fan."""
    fans = [fan]
    manager.fans = fans
    manager._dev_list = {
        "fans": fans,
    }

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
        ]
    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert hass.data[DOMAIN][VS_DEVICES] == [fan]


async def test_async_new_device_discovery(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync, fan, humidifier
) -> None:
    """Test new device discovery."""

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    # Assert platforms loaded
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert not hass.data[DOMAIN][VS_DEVICES]

    # Mock discovery of new fan which would get added to VS_DEVICES.
    with patch(
        "homeassistant.components.vesync.async_generate_device_list",
        return_value=[fan],
    ):
        await hass.services.async_call(DOMAIN, SERVICE_UPDATE_DEVS, {}, blocking=True)

        assert manager.login.call_count == 1
        assert hass.data[DOMAIN][VS_MANAGER] == manager
        assert hass.data[DOMAIN][VS_DEVICES] == [fan]

    # Mock discovery of new humidifier which would invoke discovery in all platforms.
    # The mocked humidifier needs to have all properties populated for correct processing.
    with patch(
        "homeassistant.components.vesync.async_generate_device_list",
        return_value=[humidifier],
    ):
        await hass.services.async_call(DOMAIN, SERVICE_UPDATE_DEVS, {}, blocking=True)

        assert manager.login.call_count == 1
        assert hass.data[DOMAIN][VS_MANAGER] == manager
        assert hass.data[DOMAIN][VS_DEVICES] == [fan, humidifier]


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

    humidifer: er.RegistryEntry = entity_registry.async_get_or_create(
        domain="humidifer",
        platform="vesync",
        unique_id="humidifer",
        config_entry=switch_old_id_config_entry,
        suggested_object_id="humidifer",
    )

    assert switch.unique_id == "switch"
    assert switch_old_id_config_entry.minor_version == 1
    assert humidifer.unique_id == "humidifer"

    await hass.config_entries.async_setup(switch_old_id_config_entry.entry_id)
    await hass.async_block_till_done()

    assert switch_old_id_config_entry.minor_version == 2

    migrated_switch = entity_registry.async_get(switch.entity_id)
    assert migrated_switch is not None
    assert migrated_switch.entity_id.startswith("switch")
    assert migrated_switch.unique_id == "switch-device_status"
    # Confirm humidifer was not impacted
    migrated_humidifer = entity_registry.async_get(humidifer.entity_id)
    assert migrated_humidifer is not None
    assert migrated_humidifer.unique_id == "humidifer"

    # Assert that only one entity exists in the switch domain
    switch_entities = [
        e for e in entity_registry.entities.values() if e.domain == "switch"
    ]
    assert len(switch_entities) == 1

    humidifer_entities = [
        e for e in entity_registry.entities.values() if e.domain == "humidifer"
    ]
    assert len(humidifer_entities) == 1
