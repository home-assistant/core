"""Test the UniFi Protect setup flow."""
# pylint: disable=protected-access
from __future__ import annotations

from unittest.mock import AsyncMock

from pyunifiprotect.data import Light
from pyunifiprotect.exceptions import NvrError

from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import (
    MockUFPFixture,
    generate_random_ids,
    init_entry,
    regenerate_device_ids,
)


async def test_migrate_reboot_button(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
):
    """Test migrating unique ID of reboot button."""

    light1 = light.copy()
    light1.name = "Test Light 1"
    regenerate_device_ids(light1)

    light2 = light.copy()
    light2.name = "Test Light 2"
    regenerate_device_ids(light2)

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON, DOMAIN, light1.id, config_entry=ufp.entry
    )
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light2.mac}_reboot",
        config_entry=ufp.entry,
    )

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [light1, light2], regenerate_ids=False)

    assert ufp.entry.state == ConfigEntryState.LOADED
    assert ufp.api.update.called
    assert ufp.entry.unique_id == ufp.api.bootstrap.nvr.mac

    buttons = []
    for entity in er.async_entries_for_config_entry(registry, ufp.entry.entry_id):
        if entity.domain == Platform.BUTTON.value:
            buttons.append(entity)
    assert len(buttons) == 4

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


async def test_migrate_nvr_mac(hass: HomeAssistant, ufp: MockUFPFixture, light: Light):
    """Test migrating unique ID of NVR to use MAC address."""

    light1 = light.copy()
    light1.name = "Test Light 1"
    regenerate_device_ids(light1)

    light2 = light.copy()
    light2.name = "Test Light 2"
    regenerate_device_ids(light2)

    nvr = ufp.api.bootstrap.nvr
    regenerate_device_ids(nvr)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{nvr.id}_storage_utilization",
        config_entry=ufp.entry,
    )

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [light1, light2], regenerate_ids=False)

    assert ufp.entry.state == ConfigEntryState.LOADED
    assert ufp.api.update.called
    assert ufp.entry.unique_id == ufp.api.bootstrap.nvr.mac

    assert registry.async_get(f"{Platform.SENSOR}.{DOMAIN}_storage_utilization") is None
    assert (
        registry.async_get(f"{Platform.SENSOR}.{DOMAIN}_storage_utilization_2") is None
    )
    sensor = registry.async_get(
        f"{Platform.SENSOR}.{DOMAIN}_{nvr.id}_storage_utilization"
    )
    assert sensor is not None
    assert sensor.unique_id == f"{nvr.mac}_storage_utilization"


async def test_migrate_reboot_button_no_device(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
):
    """Test migrating unique ID of reboot button if UniFi Protect device ID changed."""

    light2_id, _ = generate_random_ids()

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON, DOMAIN, light2_id, config_entry=ufp.entry
    )

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [light], regenerate_ids=False)

    assert ufp.entry.state == ConfigEntryState.LOADED
    assert ufp.api.update.called
    assert ufp.entry.unique_id == ufp.api.bootstrap.nvr.mac

    buttons = []
    for entity in er.async_entries_for_config_entry(registry, ufp.entry.entry_id):
        if entity.domain == Platform.BUTTON.value:
            buttons.append(entity)
    assert len(buttons) == 3

    entity = registry.async_get(f"{Platform.BUTTON}.unifiprotect_{light2_id.lower()}")
    assert entity is not None
    assert entity.unique_id == light2_id


async def test_migrate_reboot_button_fail(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
):
    """Test migrating unique ID of reboot button."""

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        light.id,
        config_entry=ufp.entry,
        suggested_object_id=light.display_name,
    )
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light.id}_reboot",
        config_entry=ufp.entry,
        suggested_object_id=light.display_name,
    )

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [light], regenerate_ids=False)

    assert ufp.entry.state == ConfigEntryState.LOADED
    assert ufp.api.update.called
    assert ufp.entry.unique_id == ufp.api.bootstrap.nvr.mac

    entity = registry.async_get(f"{Platform.BUTTON}.test_light")
    assert entity is not None
    assert entity.unique_id == f"{light.mac}"


async def test_migrate_device_mac_button_fail(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
):
    """Test migrating unique ID to MAC format."""

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light.id}_reboot",
        config_entry=ufp.entry,
        suggested_object_id=light.display_name,
    )
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light.mac}_reboot",
        config_entry=ufp.entry,
        suggested_object_id=light.display_name,
    )

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [light], regenerate_ids=False)

    assert ufp.entry.state == ConfigEntryState.LOADED
    assert ufp.api.update.called
    assert ufp.entry.unique_id == ufp.api.bootstrap.nvr.mac

    entity = registry.async_get(f"{Platform.BUTTON}.test_light")
    assert entity is not None
    assert entity.unique_id == f"{light.id}_reboot"


async def test_migrate_device_mac_bootstrap_fail(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
):
    """Test migrating with a network error."""

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light.id}_reboot",
        config_entry=ufp.entry,
        suggested_object_id=light.name,
    )
    registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{light.mac}_reboot",
        config_entry=ufp.entry,
        suggested_object_id=light.name,
    )

    ufp.api.get_bootstrap = AsyncMock(side_effect=NvrError)
    await init_entry(hass, ufp, [light], regenerate_ids=False)

    assert ufp.entry.state == ConfigEntryState.SETUP_RETRY
