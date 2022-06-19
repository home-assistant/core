"""Test the UniFi Protect setup flow."""
# pylint: disable=protected-access
from __future__ import annotations

from unittest.mock import AsyncMock

from pyunifiprotect.data import Light

from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MockEntityFixture, generate_random_ids, regenerate_device_ids


async def test_migrate_reboot_button(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light
):
    """Test migrating unique ID of reboot button."""

    light1 = mock_light.copy()
    light1._api = mock_entry.api
    light1.name = "Test Light 1"
    regenerate_device_ids(light1)

    light2 = mock_light.copy()
    light2._api = mock_entry.api
    light2.name = "Test Light 2"
    regenerate_device_ids(light2)

    mock_entry.api.bootstrap.lights = {
        light1.id: light1,
        light2.id: light2,
    }
    mock_entry.api.get_bootstrap = AsyncMock(return_value=mock_entry.api.bootstrap)

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON, DOMAIN, light1.id, config_entry=mock_entry.entry
    )
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light2.mac}_reboot",
        config_entry=mock_entry.entry,
    )

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac

    buttons = []
    for entity in er.async_entries_for_config_entry(
        registry, mock_entry.entry.entry_id
    ):
        if entity.domain == Platform.BUTTON.value:
            buttons.append(entity)
    assert len(buttons) == 2

    assert registry.async_get(f"{Platform.BUTTON}.test_light_1_reboot_device") is None
    assert registry.async_get(f"{Platform.BUTTON}.test_light_1_reboot_device_2") is None
    light = registry.async_get(f"{Platform.BUTTON}.unifiprotect_{light1.id.lower()}")
    assert light is not None
    assert light.unique_id == f"{light1.mac}_reboot"

    assert registry.async_get(f"{Platform.BUTTON}.test_light_2_reboot_device") is None
    assert registry.async_get(f"{Platform.BUTTON}.test_light_2_reboot_device_2") is None
    light = registry.async_get(
        f"{Platform.BUTTON}.unifiprotect_{light2.mac.lower()}_reboot"
    )
    assert light is not None
    assert light.unique_id == f"{light2.mac}_reboot"


async def test_migrate_reboot_button_no_device(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light
):
    """Test migrating unique ID of reboot button if UniFi Protect device ID changed."""

    light1 = mock_light.copy()
    light1._api = mock_entry.api
    light1.name = "Test Light 1"
    regenerate_device_ids(light1)

    light2_id, _ = generate_random_ids()

    mock_entry.api.bootstrap.lights = {
        light1.id: light1,
    }
    mock_entry.api.get_bootstrap = AsyncMock(return_value=mock_entry.api.bootstrap)

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON, DOMAIN, light2_id, config_entry=mock_entry.entry
    )

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac

    buttons = []
    for entity in er.async_entries_for_config_entry(
        registry, mock_entry.entry.entry_id
    ):
        if entity.domain == Platform.BUTTON.value:
            buttons.append(entity)
    assert len(buttons) == 2

    light = registry.async_get(f"{Platform.BUTTON}.unifiprotect_{light2_id.lower()}")
    assert light is not None
    assert light.unique_id == light2_id


async def test_migrate_reboot_button_fail(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light
):
    """Test migrating unique ID of reboot button."""

    light1 = mock_light.copy()
    light1._api = mock_entry.api
    light1.name = "Test Light 1"
    regenerate_device_ids(light1)

    mock_entry.api.bootstrap.lights = {
        light1.id: light1,
    }
    mock_entry.api.get_bootstrap = AsyncMock(return_value=mock_entry.api.bootstrap)

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        light1.id,
        config_entry=mock_entry.entry,
        suggested_object_id=light1.name,
    )
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light1.id}_reboot",
        config_entry=mock_entry.entry,
        suggested_object_id=light1.name,
    )

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac

    light = registry.async_get(f"{Platform.BUTTON}.test_light_1")
    assert light is not None
    assert light.unique_id == f"{light1.mac}"


async def test_migrate_device_mac_button_fail(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light
):
    """Test migrating unique ID to MAC format."""

    light1 = mock_light.copy()
    light1._api = mock_entry.api
    light1.name = "Test Light 1"
    regenerate_device_ids(light1)

    mock_entry.api.bootstrap.lights = {
        light1.id: light1,
    }
    mock_entry.api.get_bootstrap = AsyncMock(return_value=mock_entry.api.bootstrap)

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light1.id}_reboot",
        config_entry=mock_entry.entry,
        suggested_object_id=light1.name,
    )
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light1.mac}_reboot",
        config_entry=mock_entry.entry,
        suggested_object_id=light1.name,
    )

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac

    light = registry.async_get(f"{Platform.BUTTON}.test_light_1")
    assert light is not None
    assert light.unique_id == f"{light1.id}_reboot"
