"""Tests for VeSync services."""

from unittest.mock import AsyncMock, Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pyvesync import VeSync
from pyvesync.base_devices import VeSyncFanBase
from pyvesync.utils.errors import VeSyncError

from homeassistant.components.vesync.const import DOMAIN
from homeassistant.components.vesync.services import VeSyncService
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import mock_devices_response


@pytest.mark.usefixtures("manager")
async def test_async_new_device_discovery_no_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Service should raise when no config entry exists."""

    # Set up the config entry so the service is registered, then remove the
    # entry so the service has no entries to operate on.
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="Entry not found"):
        await hass.services.async_call(
            DOMAIN, VeSyncService.UPDATE_DEVICES, {}, blocking=True
        )


@pytest.mark.usefixtures("manager")
async def test_async_new_device_discovery_entry_not_loaded(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Service should raise when entry exists but is not loaded."""

    # Set up the config entry so the service is registered, then unload it.
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(ServiceValidationError, match="Entry not loaded"):
        await hass.services.async_call(
            DOMAIN, VeSyncService.UPDATE_DEVICES, {}, blocking=True
        )


async def test_async_new_device_discovery_error(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
) -> None:
    """Test VeSync errors are reported as translated Home Assistant errors."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    manager.get_devices = AsyncMock(side_effect=VeSyncError("API failure"))

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, VeSyncService.UPDATE_DEVICES, {}, blocking=True
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "api_response_error"


async def test_async_new_device_discovery(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    fan,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test new device discovery."""

    # Entry should not be set up yet; we'll install a fan before setup
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    # Set up the config entry (no devices initially)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    # Simulate the manager discovering a new fan when get_devices is called
    manager.get_devices = AsyncMock(
        side_effect=lambda: manager._dev_list["fans"].append(fan)
    )

    # Call the service that should trigger discovery and platform setup
    await hass.services.async_call(
        DOMAIN, VeSyncService.UPDATE_DEVICES, {}, blocking=True
    )
    await hass.async_block_till_done()

    assert manager.get_devices.call_count == 1

    # Verify an entity for the new fan was created in Home Assistant
    fan_entry = next(
        (
            e
            for e in entity_registry.entities.values()
            if e.unique_id == fan.cid and e.domain == "fan"
        ),
        None,
    )
    assert fan_entry is not None


async def test_async_new_device_discovery_fetches_details(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a discovered device gets the entities that depend on its details."""
    aioclient_mock.post(
        "https://smartapi.vesync.com/cloud/v1/deviceManaged/devices",
        json={
            "traceId": "1234",
            "code": 0,
            "msg": None,
            "result": {"total": 0, "pageSize": 0, "pageNo": 1, "list": []},
        },
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    mock_devices_response(aioclient_mock, "Air Purifier Vital 200S")

    await hass.services.async_call(
        DOMAIN, VeSyncService.UPDATE_DEVICES, {}, blocking=True
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get("select.air_purifier_vital_200s_auto_mode_preference").state
        == "default"
    )
    assert hass.states.get("sensor.air_purifier_vital_200s_filter_lifetime")


async def test_async_new_device_discovery_detail_error(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    fan,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a failed detail fetch neither skips other devices nor their entities."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    healthy_fan = Mock(
        VeSyncFanBase,
        cid="healthy-fan",
        device_type="fan",
        device_name="Healthy Fan",
        product_type="fan",
        modes=[],
        current_firm_version="1.0.0",
    )
    manager.get_devices = AsyncMock(
        side_effect=lambda: manager._dev_list["fans"].extend([fan, healthy_fan])
    )
    fan.update = AsyncMock(side_effect=VeSyncError("API failure"))

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, VeSyncService.UPDATE_DEVICES, {}, blocking=True
        )
    await hass.async_block_till_done()

    assert err.value.translation_key == "api_response_error"
    healthy_fan.update.assert_awaited_once()
    assert entity_registry.async_get_entity_id("fan", DOMAIN, fan.cid) is not None
    assert (
        entity_registry.async_get_entity_id("fan", DOMAIN, healthy_fan.cid) is not None
    )
