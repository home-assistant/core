"""Tests for Daikin services."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.daikin.const import (
    ATTR_EN_DEMAND,
    ATTR_MAX_POW,
    DOMAIN,
    KEY_MAC,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import ZoneDevice

from tests.common import MockConfigEntry

HOST = "127.0.0.1"


async def _async_setup_daikin(
    hass: HomeAssistant, zone_device: ZoneDevice
) -> MockConfigEntry:
    """Set up a Daikin config entry with a mocked library device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=zone_device.mac,
        data={CONF_HOST: HOST, KEY_MAC: zone_device.mac},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_set_demand_control(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Test the set_demand_control service."""
    zone_device.support_demand_control = True
    zone_device.set_demand_control = AsyncMock()

    await _async_setup_daikin(hass, zone_device)

    entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN, DOMAIN, zone_device.mac
    )
    assert entity_id is not None

    await hass.services.async_call(
        DOMAIN,
        "set_demand_control",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_EN_DEMAND: True,
            ATTR_MAX_POW: 40,
        },
        blocking=True,
    )

    zone_device.set_demand_control.assert_called_once_with(
        en_demand="on", max_pow=40, mode=0
    )


async def test_set_demand_control_with_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Test the set_demand_control service with an explicit mode."""
    zone_device.support_demand_control = True
    zone_device.set_demand_control = AsyncMock()

    await _async_setup_daikin(hass, zone_device)

    entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN, DOMAIN, zone_device.mac
    )
    assert entity_id is not None

    await hass.services.async_call(
        DOMAIN,
        "set_demand_control",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_EN_DEMAND: True,
            ATTR_MAX_POW: 40,
            ATTR_MODE: 2,
        },
        blocking=True,
    )

    zone_device.set_demand_control.assert_called_once_with(
        en_demand="on", max_pow=40, mode=2
    )


async def test_set_demand_control_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Test the set_demand_control service with demand control disabled."""
    zone_device.support_demand_control = True
    zone_device.set_demand_control = AsyncMock()

    await _async_setup_daikin(hass, zone_device)

    entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN, DOMAIN, zone_device.mac
    )
    assert entity_id is not None

    await hass.services.async_call(
        DOMAIN,
        "set_demand_control",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_EN_DEMAND: False,
            ATTR_MAX_POW: 40,
        },
        blocking=True,
    )

    zone_device.set_demand_control.assert_called_once_with(
        en_demand="off", max_pow=40, mode=0
    )


async def test_set_demand_control_unsupported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Test the set_demand_control service on a device that does not support it."""
    zone_device.support_demand_control = False

    await _async_setup_daikin(hass, zone_device)

    entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN, DOMAIN, zone_device.mac
    )
    assert entity_id is not None

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_demand_control",
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_EN_DEMAND: True,
                ATTR_MAX_POW: 40,
            },
            blocking=True,
        )
    assert err.value.translation_key == "demand_control_unsupported"


async def test_set_demand_control_on_zone_unsupported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Test the set_demand_control service on a zone climate entity."""
    zone_device.support_demand_control = True
    zone_device.set_demand_control = AsyncMock()

    await _async_setup_daikin(hass, zone_device)

    entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN, DOMAIN, f"{zone_device.mac}-zone0-temperature"
    )
    assert entity_id is not None

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_demand_control",
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_EN_DEMAND: True,
                ATTR_MAX_POW: 40,
            },
            blocking=True,
        )
    assert err.value.translation_key == "demand_control_zone_unsupported"
    zone_device.set_demand_control.assert_not_called()
