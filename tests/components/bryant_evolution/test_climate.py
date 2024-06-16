"""Test the BryantEvolutionClient type."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging

from evolutionhttp import BryantEvolutionClient
import pytest

from homeassistant.components.bryant_evolution.const import (
    CONF_SYSTEM_ID,
    CONF_ZONE_ID,
    DOMAIN,
)
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def _wait_for_cond(predicate: Callable[[], bool]) -> None:
    """Wait for `predicate` to return True."""
    while True:
        if predicate():
            break
        await asyncio.sleep(0.1)


class _FakeEvolutionClient(BryantEvolutionClient):
    """Fake version of `BryantEvolutionClient.

    Important design point: this type provides a `set_reads_allowed` method.
    When False, all read_ calls will hang. This allows testing that service
    call handlers on the BryantEvolutionClient type properly call
    async_write_ha_state (since async_update cannot complete when reads are
    paused).
    """

    def __init__(self) -> None:
        super().__init__("UNUSED", 1, 1)
        self._temp = 75
        self._mode = "COOL"
        self._clsp = 72
        self._htsp = None
        self._fan = "AUTO"
        self._allow_reads = True
        self._allow_reads_cond = asyncio.Condition()

    async def read_current_temperature(self) -> int | None:
        async with self._allow_reads_cond:
            await self._allow_reads_cond.wait_for(self._are_reads_allowed)
            return self._temp

    async def read_cooling_setpoint(self) -> int | None:
        async with self._allow_reads_cond:
            await self._allow_reads_cond.wait_for(self._are_reads_allowed)
            return self._clsp

    async def read_heating_setpoint(self) -> int | None:
        async with self._allow_reads_cond:
            await self._allow_reads_cond.wait_for(self._are_reads_allowed)
            return self._htsp

    def _are_reads_allowed(self) -> bool:
        return self._allow_reads

    async def read_fan_mode(self) -> str | None:
        async with self._allow_reads_cond:
            await self._allow_reads_cond.wait_for(self._are_reads_allowed)
            return self._fan

    async def set_cooling_setpoint(self, temperature: int) -> bool:
        async with self._allow_reads_cond:
            self._clsp = temperature
            return True

    async def set_heating_setpoint(self, temperature: int) -> bool:
        async with self._allow_reads_cond:
            self._htsp = temperature
            return True

    async def read_hvac_mode(self) -> tuple[str, bool] | None:
        async with self._allow_reads_cond:
            await self._allow_reads_cond.wait_for(self._are_reads_allowed)
            return (self._mode, False)

    async def set_fan_mode(self, fan_mode: str) -> bool:
        async with self._allow_reads_cond:
            self._fan = fan_mode
            return True

    async def set_allow_reads(self, allow: bool) -> None:
        async with self._allow_reads_cond:
            self._allow_reads = allow
            self._allow_reads_cond.notify_all()

    async def set_hvac_mode(self, hvac_mode: HVACMode) -> bool:
        async with self._allow_reads_cond:
            self._mode = hvac_mode
            return True


@pytest.fixture
async def mock_evolution_entry(
    hass: HomeAssistant,
) -> MockConfigEntry[BryantEvolutionClient]:
    """Configure and return a Bryant evolution integration."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "localhost", CONF_SYSTEM_ID: 1, CONF_ZONE_ID: 1},
    )
    entry.runtime_data = _FakeEvolutionClient()
    entry.add_to_hass(hass)

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.CLIMATE])
    await hass.async_block_till_done()

    return entry


async def test_setup_integration(
    hass: HomeAssistant, mock_evolution_entry: MockConfigEntry[BryantEvolutionClient]
) -> None:
    """Test that an instance can be constructed."""
    state = hass.states.get("climate.bryant_evolution_system_1_zone_1")
    assert state.state == "cool"
    assert state.attributes["fan_mode"] == "AUTO"
    assert state.attributes["current_temperature"] == 75
    assert state.attributes["temperature"] == 72


async def test_set_temperature(
    hass: HomeAssistant, mock_evolution_entry: MockConfigEntry[BryantEvolutionClient]
) -> None:
    """Test that setting target temperature HEAT and COOL modes works."""

    @dataclass
    class TestCase:
        mode: HVACMode
        initial_temp: int
        new_temp: int
        temp_reader: Callable[[BryantEvolutionClient], int]

    testcases = [
        TestCase(
            HVACMode.COOL,
            90,
            80,
            lambda client: client.read_cooling_setpoint(),
        ),
        TestCase(HVACMode.HEAT, 40, 50, lambda client: client.read_heating_setpoint()),
    ]
    client = mock_evolution_entry.runtime_data
    for case in testcases:
        # Enter case.mode with a known setpoint.
        data = {"hvac_mode": case.mode}
        data[ATTR_ENTITY_ID] = "climate.bryant_evolution_system_1_zone_1"
        await hass.services.async_call(
            "climate", SERVICE_SET_HVAC_MODE, data, blocking=True
        )
        data = {"temperature": case.initial_temp}
        data[ATTR_ENTITY_ID] = "climate.bryant_evolution_system_1_zone_1"
        await hass.services.async_call(
            "climate", SERVICE_SET_TEMPERATURE, data, blocking=True
        )
        state = hass.states.get("climate.bryant_evolution_system_1_zone_1")
        assert state.attributes["temperature"] == case.initial_temp
        assert await case.temp_reader(client) == case.initial_temp
        assert await client.read_hvac_mode() == (case.mode.lower(), False)

        # Change the setpoint, pausing reads to the device so that we
        # verify that changes are locally committed.
        await mock_evolution_entry.runtime_data.set_allow_reads(False)
        data = {"temperature": case.new_temp}
        data[ATTR_ENTITY_ID] = "climate.bryant_evolution_system_1_zone_1"
        await hass.services.async_call(
            "climate", SERVICE_SET_TEMPERATURE, data, blocking=False
        )
        state = hass.states.get("climate.bryant_evolution_system_1_zone_1")
        await _wait_for_cond(
            lambda case=case,
            s=hass.states.get("climate.bryant_evolution_system_1_zone_1"): s.attributes[
                "temperature"
            ]
            == case.new_temp
        )
        await mock_evolution_entry.runtime_data.set_allow_reads(True)
        assert await case.temp_reader(client) == case.new_temp
        await hass.async_block_till_done()


async def test_set_temperature_mode_heat_cool(
    hass: HomeAssistant, mock_evolution_entry: MockConfigEntry[BryantEvolutionClient]
) -> None:
    """Test that changing the setpoint in HEAT_COOL mode works."""
    client = mock_evolution_entry.runtime_data

    data = {"hvac_mode": HVACMode.HEAT_COOL}
    data[ATTR_ENTITY_ID] = "climate.bryant_evolution_system_1_zone_1"
    await hass.services.async_call(
        "climate", SERVICE_SET_HVAC_MODE, data, blocking=True
    )
    data = {"target_temp_low": 50, "target_temp_high": 90}
    data[ATTR_ENTITY_ID] = "climate.bryant_evolution_system_1_zone_1"
    await hass.services.async_call(
        "climate", SERVICE_SET_TEMPERATURE, data, blocking=True
    )
    state = hass.states.get("climate.bryant_evolution_system_1_zone_1")
    assert state.attributes["target_temp_low"] == 50
    assert state.attributes["target_temp_high"] == 90
    assert await client.read_cooling_setpoint() == 90
    assert await client.read_heating_setpoint() == 50
    assert await client.read_hvac_mode() == ("auto", False)

    # Change the setpoint, pausing reads to the device so that we
    # verify that changes are locally committed.
    await mock_evolution_entry.runtime_data.set_allow_reads(False)
    data = {"target_temp_low": 70, "target_temp_high": 80}
    data[ATTR_ENTITY_ID] = "climate.bryant_evolution_system_1_zone_1"
    await hass.services.async_call(
        "climate", SERVICE_SET_TEMPERATURE, data, blocking=False
    )
    await _wait_for_cond(
        lambda s=hass.states.get(
            "climate.bryant_evolution_system_1_zone_1"
        ): s.attributes["target_temp_low"] == 70
        and s.attributes["target_temp_high"] == 80
    )
    await mock_evolution_entry.runtime_data.set_allow_reads(True)
    await hass.async_block_till_done()


async def test_set_fan_mode(
    hass: HomeAssistant, mock_evolution_entry: MockConfigEntry[BryantEvolutionClient]
) -> None:
    """Test that setting fan mode works."""
    fan_modes = ["AUTO", "LOW", "MED", "HIGH"]
    client = mock_evolution_entry.runtime_data
    for mode in fan_modes:
        # Change the fan mode, pausing reads to the device so that we
        # verify that changes are locally committed.
        await mock_evolution_entry.runtime_data.set_allow_reads(False)
        data = {ATTR_FAN_MODE: mode}
        data[ATTR_ENTITY_ID] = "climate.bryant_evolution_system_1_zone_1"
        await hass.services.async_call(
            "climate", SERVICE_SET_FAN_MODE, data, blocking=False
        )
        await _wait_for_cond(
            lambda mode=mode,
            s=hass.states.get("climate.bryant_evolution_system_1_zone_1"): s.attributes[
                ATTR_FAN_MODE
            ]
            == mode
        )
        await mock_evolution_entry.runtime_data.set_allow_reads(True)
        await hass.async_block_till_done()
        assert await client.read_fan_mode() == mode
