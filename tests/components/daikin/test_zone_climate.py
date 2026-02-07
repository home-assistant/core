"""Tests for Daikin zone climate entities."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
import urllib.parse

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
from homeassistant.components.daikin.const import DOMAIN as DAIKIN_DOMAIN, KEY_MAC
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

from tests.common import MockConfigEntry

HOST = "127.0.0.1"


class FakeZoneDevice:
    """Fake Daikin device exposing zone temperature control."""

    def __init__(
        self,
        *,
        zones: list[list[str | int]],
        target_temperature: float | None = 22,
        mode: str = "hot",
        heating_values: str | None = None,
        cooling_values: str | None = None,
    ) -> None:
        """Initialize the fake zone-capable device."""
        self.mac = "001122334455"
        self.target_temperature = target_temperature
        self.zones = zones
        self.fan_rate = []
        self.swing_modes = []
        self.support_away_mode = False
        self.support_advanced_modes = False
        self.support_fan_rate = False
        self.support_swing_mode = False
        self.support_outside_temperature = False
        self.support_energy_consumption = False
        self.support_humidity = False
        self.support_compressor_frequency = False
        self.compressor_frequency = 0
        self.inside_temperature = 21.0
        self.outside_temperature = 13.0
        self.humidity = 40
        self.current_total_power_consumption = 0.0
        self.last_hour_cool_energy_consumption = 0.0
        self.last_hour_heat_energy_consumption = 0.0
        self.today_energy_consumption = 0.0
        self.today_total_energy_consumption = 0.0
        self._mode = mode

        encoded_zone_temperatures = ";".join(str(zone[2]) for zone in zones)
        self.values: dict[str, Any] = {
            "name": "Daikin Test",
            "model": "TESTMODEL",
            "ver": "1_0_0",
            "zone_name": ";".join(str(zone[0]) for zone in zones),
            "zone_onoff": ";".join(str(zone[1]) for zone in zones),
            "lztemp_h": (
                encoded_zone_temperatures if heating_values is None else heating_values
            ),
            "lztemp_c": (
                encoded_zone_temperatures if cooling_values is None else cooling_values
            ),
        }

    async def update_status(self) -> None:
        """Simulate a status refresh."""

    async def set(self, values: dict[str, Any]) -> None:
        """Simulate setting main unit values."""
        if mode := values.get("mode"):
            self._mode = mode

    async def set_zone(self, zone_id: int, key: str, value: str) -> None:
        """Simulate setting a zone value."""
        if key not in {"zone_onoff", "lztemp_h", "lztemp_c"}:
            raise KeyError(key)

        if key == "zone_onoff":
            zone_states = self.values["zone_onoff"].split(";")
            zone_states[zone_id] = value
            self.values["zone_onoff"] = ";".join(zone_states)
            self.zones[zone_id][1] = value
            return

        zone_temperatures = self.values[key].split(";")
        zone_temperatures[zone_id] = value
        self.values[key] = ";".join(zone_temperatures)
        self.zones[zone_id][2] = int(value)

    async def set_holiday(self, _state: str) -> None:
        """Simulate setting holiday mode."""

    async def set_advanced_mode(self, _mode: str, _state: str) -> None:
        """Simulate setting an advanced mode."""

    async def set_streamer(self, _state: str) -> None:
        """Simulate setting streamer mode."""

    def represent(self, key: str) -> tuple[None, list[str] | str]:
        """Return decoded data for the requested key."""
        if key == "lztemp_h":
            decoded = urllib.parse.unquote(self.values["lztemp_h"])
            return (None, decoded.split(";") if decoded else [])
        if key == "lztemp_c":
            decoded = urllib.parse.unquote(self.values["lztemp_c"])
            return (None, decoded.split(";") if decoded else [])
        if key == "mode":
            return (None, self._mode)
        if key == "f_rate":
            return (None, "auto")
        if key == "f_dir":
            return (None, "3d")
        if key == "en_hol":
            return (None, "off")
        if key == "adv":
            return (None, "")
        if key == "htemp":
            return (None, str(self.inside_temperature))
        if key == "otemp":
            return (None, str(self.outside_temperature))
        if key == "stemp":
            return (
                None,
                "" if self.target_temperature is None else str(self.target_temperature),
            )
        return (None, "")


async def _async_setup_daikin(
    hass: HomeAssistant, device: FakeZoneDevice
) -> MockConfigEntry:
    """Set up a Daikin config entry with a mocked library device."""
    config_entry = MockConfigEntry(
        domain=DAIKIN_DOMAIN,
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
    entity_registry: er.EntityRegistry, device: FakeZoneDevice, zone_id: int
) -> str | None:
    """Return the entity id for a zone climate unique id."""
    return entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN,
        DAIKIN_DOMAIN,
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


@pytest.mark.asyncio
async def test_setup_entry_adds_zone_climates(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Configured zones create zone climate entities."""
    device = FakeZoneDevice(
        zones=[["-", "0", 0], ["Living", "1", 22], ["Office", "1", 21]]
    )

    await _async_setup_daikin(hass, device)

    assert _zone_entity_id(entity_registry, device, 0) is None
    assert _zone_entity_id(entity_registry, device, 1) is not None
    assert _zone_entity_id(entity_registry, device, 2) is not None


@pytest.mark.asyncio
async def test_setup_entry_skips_zone_climates_without_support(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Missing zone temperature lists skip zone climate entities."""
    device = FakeZoneDevice(zones=[["Living", "1", 22]])
    device.values["lztemp_h"] = ""
    device.values["lztemp_c"] = ""

    await _async_setup_daikin(hass, device)

    assert _zone_entity_id(entity_registry, device, 0) is None


@pytest.mark.asyncio
async def test_zone_climate_sets_temperature_heating(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Setting temperature updates the heating zone value."""
    device = FakeZoneDevice(zones=[["Living", "1", 22], ["Office", "1", 21]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    await _async_set_zone_temperature(hass, entity_id, 23)

    assert device.represent("lztemp_h")[1][0] == "23"
    assert device.represent("lztemp_c")[1][0] == "22"


@pytest.mark.asyncio
async def test_zone_climate_sets_temperature_cooling(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Setting temperature in cool mode updates the cooling list."""
    device = FakeZoneDevice(
        zones=[["Living", "1", 22], ["Office", "1", 21]],
        mode="cool",
    )
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    await _async_set_zone_temperature(hass, entity_id, 23)

    assert device.represent("lztemp_h")[1][0] == "22"
    assert device.represent("lztemp_c")[1][0] == "23"


@pytest.mark.asyncio
async def test_zone_climate_rejects_out_of_range_temperature(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Service validation rejects values outside the allowed range."""
    device = FakeZoneDevice(zones=[["Living", "1", 22]], target_temperature=22)
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    with pytest.raises(ServiceValidationError) as err:
        await _async_set_zone_temperature(hass, entity_id, 30)

    assert err.value.translation_key == "temp_out_of_range"


@pytest.mark.asyncio
async def test_zone_climate_keeps_zone_disabled(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Setting temperature does not toggle a disabled zone."""
    device = FakeZoneDevice(zones=[["Living", "0", 22]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    await _async_set_zone_temperature(hass, entity_id, 21)

    assert device.values["zone_onoff"] == "0"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 21.0


@pytest.mark.asyncio
async def test_zone_climate_available_when_zone_disabled(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Disabled zones stay available when supported parameters exist."""
    device = FakeZoneDevice(zones=[["Living", "0", 22]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_zone_climate_unavailable_without_target_temperature(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Zones are unavailable if system target temperature is missing."""
    device = FakeZoneDevice(zones=[["Living", "1", 22]], target_temperature=None)
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_zone_climate_zone_inactive_after_setup(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Inactive zones raise a translated error during service calls."""
    device = FakeZoneDevice(zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None
    device.zones[0][0] = "-"

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_inactive"


@pytest.mark.asyncio
async def test_zone_climate_zone_missing_after_setup(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Missing zones raise a translated error during service calls."""
    device = FakeZoneDevice(zones=[["Living", "1", 22], ["Office", "1", 22]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 1)
    assert entity_id is not None
    device.zones = [["Living", "1", 22]]

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_missing"


@pytest.mark.asyncio
async def test_zone_climate_parameters_unavailable(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Missing zone parameter lists make the zone entity unavailable."""
    device = FakeZoneDevice(zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None
    device.values["lztemp_h"] = ""
    device.values["lztemp_c"] = ""

    await async_update_entity(hass, entity_id)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_zone_climate_hvac_modes_read_only(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Changing HVAC mode through a zone climate is blocked."""
    device = FakeZoneDevice(zones=[["Living", "1", 22]])
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


@pytest.mark.asyncio
async def test_zone_climate_set_temperature_requires_heat_or_cool(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Setting temperature in unsupported modes raises a translated error."""
    device = FakeZoneDevice(zones=[["Living", "1", 22]], mode="auto")
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_hvac_mode_unsupported"


@pytest.mark.asyncio
async def test_zone_climate_properties(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Zone climate exposes expected state attributes."""
    device = FakeZoneDevice(
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


@pytest.mark.asyncio
async def test_zone_climate_target_temperature_inactive_mode(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """In non-heating/cooling modes, zone target temperature is None."""
    device = FakeZoneDevice(
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


@pytest.mark.asyncio
async def test_zone_climate_set_zone_failed(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Service call surfaces backend zone update errors."""
    device = FakeZoneDevice(zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, device)
    entity_id = _zone_entity_id(entity_registry, device, 0)
    assert entity_id is not None
    device.set_zone = AsyncMock(side_effect=NotImplementedError)

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_set_failed"
