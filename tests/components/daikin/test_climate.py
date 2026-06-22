"""Tests for Daikin climate entities."""

import pytest

from homeassistant.components.climate import (
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    HVACMode,
)
from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ZoneDevice, configure_zone_device

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


@pytest.mark.parametrize(
    ("daikin_mode", "hvac_mode", "expected_min", "expected_max"),
    [
        pytest.param("cool", HVACMode.COOL, 18.0, 32.0, id="cooling_limits"),
        pytest.param("hot", HVACMode.HEAT, 10.0, 30.0, id="heating_limits"),
        pytest.param("auto", HVACMode.HEAT_COOL, 16.0, 32.0, id="auto_limits"),
        pytest.param("dry", HVACMode.DRY, 16.0, 32.0, id="dry_limits"),
        pytest.param("fan", HVACMode.FAN_ONLY, 16.0, 32.0, id="fan_only_limits"),
        pytest.param("off", HVACMode.OFF, 16.0, 32.0, id="off_limits"),
    ],
)
async def test_daikin_climate_dynamic_temperature_limits(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    daikin_mode: str,
    hvac_mode: HVACMode,
    expected_min: float,
    expected_max: float,
) -> None:
    """Test that DaikinClimate reports dynamic min_temp and max_temp based on HVAC mode."""
    configure_zone_device(
        zone_device,
        zones=[["Living", "1", 22]],
        mode=daikin_mode,
    )

    await _async_setup_daikin(hass, zone_device)

    entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN,
        DOMAIN,
        zone_device.mac,
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == hvac_mode
    assert state.attributes[ATTR_MIN_TEMP] == expected_min
    assert state.attributes[ATTR_MAX_TEMP] == expected_max
