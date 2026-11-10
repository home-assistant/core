"""Tests for the light module."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pyvesync import VeSync
from pyvesync.base_devices.bulb_base import VeSyncBulb
from pyvesync.const import ProductTypes
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.vesync.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, mock_devices_response


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_light_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    # Configure the API devices call for device_name
    mock_devices_response(aioclient_mock, device_name)

    # setup platform - only including the named device
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check device registry
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    # Check entity registry
    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == LIGHT_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


async def _async_setup_bulb(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    bulb: Mock,
) -> str:
    """Set up the light platform with a single bulb and return its entity ID."""
    manager.devices.bulbs.append(bulb)

    with patch("homeassistant.components.vesync.PLATFORMS", [Platform.LIGHT]):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(LIGHT_DOMAIN, DOMAIN, bulb.cid)
    assert entity_id is not None
    return entity_id


async def test_tunable_light_turn_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test turning on a tunable bulb with color temperature and brightness."""
    bulb = Mock(
        VeSyncBulb,
        cid="tunable_bulb",
        device_type="ESL100CW",
        device_name="Tunable Bulb",
        product_type=ProductTypes.BULB,
        sub_device_no=None,
        current_firm_version="1.0.0",
        supports_color_temp=True,
        supports_brightness=True,
        state=SimpleNamespace(
            connection_status="online",
            device_status="off",
            brightness=75,
            color_temp=50,
        ),
        set_color_temp=AsyncMock(),
        set_brightness=AsyncMock(),
        turn_on=AsyncMock(),
        turn_off=AsyncMock(),
    )
    entity_id = await _async_setup_bulb(
        hass, config_entry, manager, entity_registry, bulb
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_COLOR_TEMP_KELVIN: 6500,
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )
    bulb.set_color_temp.assert_awaited_once_with(100)
    bulb.set_brightness.assert_awaited_once_with(50)
    bulb.turn_on.assert_not_awaited()


async def test_dimmable_light_turn_on_and_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a dimmable bulb through the light services."""
    bulb = Mock(
        VeSyncBulb,
        cid="dimmable_bulb",
        device_type="ESL100",
        device_name="Dimmable Bulb",
        product_type=ProductTypes.BULB,
        sub_device_no=None,
        current_firm_version="1.0.0",
        supports_color_temp=False,
        supports_brightness=True,
        state=SimpleNamespace(
            connection_status="online",
            device_status="on",
            brightness=None,
            color_temp=None,
        ),
        set_brightness=AsyncMock(),
        turn_on=AsyncMock(),
        turn_off=AsyncMock(),
    )
    entity_id = await _async_setup_bulb(
        hass, config_entry, manager, entity_registry, bulb
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_BRIGHTNESS] == 0

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 1},
        blocking=True,
    )
    bulb.set_brightness.assert_awaited_once_with(1)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    bulb.turn_on.assert_awaited_once_with()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    bulb.turn_off.assert_awaited_once_with()
