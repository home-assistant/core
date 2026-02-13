"""Tests for Daikin zone climate entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_HOST,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import ZoneDeviceFactory

from tests.common import MockConfigEntry

HOST = "127.0.0.1"


async def _async_setup_daikin(
    hass: HomeAssistant, device: MagicMock
) -> MockConfigEntry:
    """Set up a Daikin config entry with a mocked library device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=device.mac,
        data={CONF_HOST: HOST, KEY_MAC: device.mac},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.daikin.DaikinFactory",
        new=AsyncMock(return_value=device),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


def _zone_entity_id(
    entity_registry: er.EntityRegistry, device: MagicMock, zone_id: int
) -> str | None:
    """Return the entity id for a zone climate unique id."""
    return entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN,
        DOMAIN,
        f"{device.mac}-zone{zone_id}-temperature",
    )


async def _async_set_zone_temperature(
    hass: HomeAssistant, entity_id: str, temperature: float
) -> None:
    """Call `climate.set_temperature` for a zone climate."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TEMPERATURE: temperature,
        },
        blocking=True,
    )


async def test_setup_entry_adds_zone_climates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """Configured zones create zone climate entities."""
    device = zone_device_factory(
        zones=[["-", "0", 0], ["Living", "1", 22], ["Office", "1", 21]]
    )

    await _async_setup_daikin(hass, device)

    assert _zone_entity_id(entity_registry, device, 0) is None
    assert _zone_entity_id(entity_registry, device, 1) is not None
    assert _zone_entity_id(entity_registry, device, 2) is not None


async def test_setup_entry_skips_zone_climates_without_support(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """Missing zone temperature lists skip zone climate entities."""
    device = zone_device_factory(zones=[["Living", "1", 22]])
    device.values["lztemp_h"] = ""
    device.values["lztemp_c"] = ""

    await _async_setup_daikin(hass, device)

    assert _zone_entity_id(entity_registry, device, 0) is None


@pytest.mark.parametrize(
    ("mode", "expected_zone_key"),
    [("hot", "lztemp_h"), ("cool", "lztemp_c")],
)
async def test_zone_climate_sets_temperature_for_active_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
    mode: str,
    expected_zone_key: str,
) -> None:
    """Setting temperature updates the active mode zone value."""
    device = zone_device_factory(
        zones=[["Living", "1", 22], ["Office", "1", 21]],
        mode=mode,
    )
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    await _async_set_zone_temperature(hass, entity_id, 23)

    device.set_zone.assert_awaited_once_with(0, expected_zone_key, "23")


async def test_zone_climate_rejects_out_of_range_temperature(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """Service validation rejects values outside the allowed range."""
    device = zone_device_factory(zones=[["Living", "1", 22]], target_temperature=22)
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    with pytest.raises(ServiceValidationError) as err:
        await _async_set_zone_temperature(hass, entity_id, 30)

    assert err.value.translation_key == "temp_out_of_range"


async def test_zone_climate_unavailable_without_target_temperature(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """Zones are unavailable if system target temperature is missing."""
    device = zone_device_factory(zones=[["Living", "1", 22]], target_temperature=None)
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_zone_climate_zone_inactive_after_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """Inactive zones raise a translated error during service calls."""
    device = zone_device_factory(zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None
    device.zones[0][0] = "-"

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_inactive"


async def test_zone_climate_zone_missing_after_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """Missing zones raise a translated error during service calls."""
    device = zone_device_factory(zones=[["Living", "1", 22], ["Office", "1", 22]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 1)
    assert entity_id is not None
    device.zones = [["Living", "1", 22]]

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_missing"


async def test_zone_climate_parameters_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """Missing zone parameter lists make the zone entity unavailable."""
    device = zone_device_factory(zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None
    device.values["lztemp_h"] = ""
    device.values["lztemp_c"] = ""

    await async_update_entity(hass, entity_id)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_zone_climate_hvac_modes_read_only(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """Changing HVAC mode through a zone climate is blocked."""
    device = zone_device_factory(zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )

    assert err.value.translation_key == "zone_hvac_read_only"


async def test_zone_climate_set_temperature_requires_heat_or_cool(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """Setting temperature in unsupported modes raises a translated error."""
    device = zone_device_factory(zones=[["Living", "1", 22]], mode="auto")
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_hvac_mode_unsupported"


async def test_zone_climate_properties(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """Zone climate exposes expected state attributes."""
    device = zone_device_factory(
        zones=[["Living", "1", 22]],
        target_temperature=24,
        mode="cool",
        heating_values="20",
        cooling_values="18",
    )
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert state.attributes[ATTR_TEMPERATURE] == 18.0
    assert state.attributes[ATTR_MIN_TEMP] == 22.0
    assert state.attributes[ATTR_MAX_TEMP] == 26.0
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.COOL]
    assert state.attributes["zone_id"] == 0


async def test_zone_climate_target_temperature_inactive_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """In non-heating/cooling modes, zone target temperature is None."""
    device = zone_device_factory(
        zones=[["Living", "1", 22]],
        mode="auto",
        heating_values="bad",
        cooling_values="19",
    )
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_zone_climate_set_zone_failed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device_factory: ZoneDeviceFactory,
) -> None:
    """Service call surfaces backend zone update errors."""
    device = zone_device_factory(zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None
    device.set_zone = AsyncMock(side_effect=NotImplementedError)

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_set_failed"
