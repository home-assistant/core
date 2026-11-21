"""Tests for Netatmo repairs."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.netatmo.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .common import (
    HOME_ID,
    LEGACY_CLIMATE_ISSUE_ID,
    add_disabled_home_with_schedule_select,
    selected_platforms,
)


async def test_legacy_climate_fix_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test the fix enables the home and hides only the schedule select."""
    device, entity = add_disabled_home_with_schedule_select(
        device_registry, entity_registry, config_entry, "Home"
    )
    assert await async_setup_component(hass, "repairs", {})

    with selected_platforms([Platform.CLIMATE, Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        client = await hass_client()
        data = await start_repair_fix_flow(client, DOMAIN, LEGACY_CLIMATE_ISSUE_ID)
        assert data["step_id"] == "confirm"
        assert data["description_placeholders"] == {"home_name": "MYHOME"}

        data = await process_repair_fix_flow(client, data["flow_id"], {})
        assert data["type"] == "create_entry"

        # Enabling the home device reloads the entry
        await hass.async_block_till_done()

    home_device = device_registry.async_get(device.id)
    assert home_device is not None
    assert home_device.disabled_by is None

    select = entity_registry.async_get(entity.id)
    assert select is not None
    assert select.disabled_by is er.RegistryEntryDisabler.USER

    assert HOME_ID in config_entry.runtime_data.account.homes
    assert issue_registry.async_get_issue(DOMAIN, LEGACY_CLIMATE_ISSUE_ID) is None


async def test_legacy_climate_fix_flow_without_schedule_select(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test the fix still enables the home after the select was removed."""
    device, entity = add_disabled_home_with_schedule_select(
        device_registry, entity_registry, config_entry, "Home"
    )
    assert await async_setup_component(hass, "repairs", {})

    with selected_platforms([Platform.CLIMATE, Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        entity_registry.async_remove(entity.entity_id)

        client = await hass_client()
        data = await start_repair_fix_flow(client, DOMAIN, LEGACY_CLIMATE_ISSUE_ID)
        data = await process_repair_fix_flow(client, data["flow_id"], {})
        assert data["type"] == "create_entry"

        await hass.async_block_till_done()

    home_device = device_registry.async_get(device.id)
    assert home_device is not None
    assert home_device.disabled_by is None
    assert HOME_ID in config_entry.runtime_data.account.homes
    assert issue_registry.async_get_issue(DOMAIN, LEGACY_CLIMATE_ISSUE_ID) is None


async def test_legacy_climate_fix_flow_home_removed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test the fix aborts when the home device is gone before confirming."""
    device, _ = add_disabled_home_with_schedule_select(
        device_registry, entity_registry, config_entry, "Home"
    )
    assert await async_setup_component(hass, "repairs", {})

    with selected_platforms([Platform.CLIMATE, Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        client = await hass_client()
        data = await start_repair_fix_flow(client, DOMAIN, LEGACY_CLIMATE_ISSUE_ID)

        device_registry.async_remove_device(device.id)

        data = await process_repair_fix_flow(client, data["flow_id"], {})
        assert data["type"] == "abort"
        assert data["reason"] == "home_removed"
