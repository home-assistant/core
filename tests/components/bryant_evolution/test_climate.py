"""Test the BryantEvolutionClient type."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from unittest.mock import patch

from evolutionhttp import BryantEvolutionLocalClient
import pytest

from homeassistant.components.bryant_evolution.const import CONF_SYSTEM_ZONE, DOMAIN
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def _wait_for_cond(predicate: Callable[[], bool]) -> None:
    """Wait for `predicate` to return True."""
    while True:
        if predicate():
            break
        await asyncio.sleep(0.1)


class _FakeEvolutionClient(BryantEvolutionLocalClient):
    """Fake version of `BryantEvolutionClient.

    Important design point: this type provides a `set_allow_reads` method.
    When False, all read_* calls will hang. This allows testing that service
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
        self._is_active = False

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
            if not self._mode:
                return None
            return (self._mode, self._is_active)

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

    async def set_is_active(self, is_active: bool) -> None:
        async with self._allow_reads_cond:
            self._is_active = is_active


@pytest.fixture
async def mock_evolution_entry(
    hass: HomeAssistant,
) -> MockConfigEntry:
    """Configure and return a Bryant evolution integration."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    with patch(
        "evolutionhttp.BryantEvolutionLocalClient.get_client",
        return_value=_FakeEvolutionClient(),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_FILENAME: "/dev/ttyUSB0", CONF_SYSTEM_ZONE: [(1, 1)]},
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry


async def test_setup_integration_success(
    hass: HomeAssistant, mock_evolution_entry: MockConfigEntry
) -> None:
    """Test that an instance can be constructed."""
    state = hass.states.get("climate.system_1_zone_1")
    assert state, (x.name() for x in hass.states.async_all())
    assert state.state == "cool"
    assert state.attributes["fan_mode"] == "auto"
    assert state.attributes["current_temperature"] == 75
    assert state.attributes["temperature"] == 72


async def test_setup_integration_prevented_by_unavailable_client(
    hass: HomeAssistant,
) -> None:
    """Test that setup throws ConfigEntryNotReady when the client is unavailable."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_evolution_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            # This file does not exist.
            CONF_FILENAME: "test_setup_integration_prevented_by_unavailable_client",
            CONF_SYSTEM_ZONE: [(1, 1)],
        },
    )
    mock_evolution_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_evolution_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_evolution_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_integration_client_returns_none(hass: HomeAssistant) -> None:
    """Test that an instance can be constructed from an unavailable client."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    with patch(
        "evolutionhttp.BryantEvolutionLocalClient.get_client",
        return_value=_FakeEvolutionClient(),
    ) as p:
        mock_evolution_entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_FILENAME: "/dev/ttyUSB0", CONF_SYSTEM_ZONE: [(1, 1)]},
        )
        client = p.return_value
        client._fan = None
        client._clsp = None
        client._htsp = None
        mock_evolution_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_evolution_entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get("climate.system_1_zone_1")
        assert state, hass.states.async_all()


async def test_setup_multiple_systems_zones(hass: HomeAssistant) -> None:
    """Test that a device with multiple systems and zones works."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    clients = {
        (1, 1): _FakeEvolutionClient(),
        (1, 2): _FakeEvolutionClient(),
        (2, 3): _FakeEvolutionClient(),
    }
    clients[(1, 1)]._clsp = 1
    clients[(1, 2)]._clsp = 2
    clients[(2, 3)]._clsp = 3
    with patch(
        "evolutionhttp.BryantEvolutionLocalClient.get_client",
        side_effect=lambda system, zone, tty: clients[(system, zone)],
    ):
        mock_evolution_entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_FILENAME: "/dev/ttyUSB0", CONF_SYSTEM_ZONE: clients.keys()},
        )
        mock_evolution_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_evolution_entry.entry_id)
        await hass.async_block_till_done()

    # Check that each system and zone has the expected temperature value to
    # verify that the initial setup flow worked as expected.
    for sz in clients:  # Use clients keyset to enumerate systems and zones
        system = sz[0]
        zone = sz[1]
        state = hass.states.get(f"climate.system_{system}_zone_{zone}")
        assert state, hass.states.async_all()
        assert state.attributes["temperature"] == zone

    # Check that the created devices are wired to each other as expected.
    device_registry = dr.async_get(hass)
    _LOGGER.error("XXX mock entryid: %s", mock_evolution_entry.entry_id)

    def find_device(name):
        return next(filter(lambda x: x.name == name, device_registry.devices.values()))

    sam = find_device("System Access Module")
    s1 = find_device("System 1")
    s2 = find_device("System 2")
    s1z1 = find_device("System 1 Zone 1")
    s1z2 = find_device("System 1 Zone 2")
    s2z3 = find_device("System 2 Zone 3")

    assert sam.via_device_id is None
    assert s1.via_device_id == sam.id
    assert s2.via_device_id == sam.id
    assert s1z1.via_device_id == s1.id
    assert s1z2.via_device_id == s1.id
    assert s2z3.via_device_id == s2.id


async def test_set_temperature(
    hass: HomeAssistant, mock_evolution_entry: MockConfigEntry
) -> None:
    """Test that setting target temperature HEAT and COOL modes works."""

    @dataclass
    class TestCase:
        mode: HVACMode
        initial_temp: int
        new_temp: int
        temp_reader: Callable[[BryantEvolutionLocalClient], int]

    testcases = [
        TestCase(
            HVACMode.COOL,
            90,
            80,
            lambda client: client.read_cooling_setpoint(),
        ),
        TestCase(HVACMode.HEAT, 40, 50, lambda client: client.read_heating_setpoint()),
    ]
    client = mock_evolution_entry.runtime_data[(1, 1)]
    for case in testcases:
        # Enter case.mode with a known setpoint.
        data = {"hvac_mode": case.mode}
        data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
        await hass.services.async_call(
            "climate", SERVICE_SET_HVAC_MODE, data, blocking=True
        )
        data = {"temperature": case.initial_temp}
        data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
        await hass.services.async_call(
            "climate", SERVICE_SET_TEMPERATURE, data, blocking=True
        )
        state = hass.states.get("climate.system_1_zone_1")
        assert state.attributes["temperature"] == case.initial_temp
        assert await case.temp_reader(client) == case.initial_temp
        assert await client.read_hvac_mode() == (case.mode.lower(), False)

        # Change the setpoint, pausing reads to the device so that we
        # verify that changes are locally committed.
        await client.set_allow_reads(False)
        data = {"temperature": case.new_temp}
        data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
        await hass.services.async_call(
            "climate", SERVICE_SET_TEMPERATURE, data, blocking=False
        )
        state = hass.states.get("climate.system_1_zone_1")
        await _wait_for_cond(
            lambda case=case,
            s=hass.states.get("climate.system_1_zone_1"): s.attributes["temperature"]
            == case.new_temp
        )
        await client.set_allow_reads(True)
        assert await case.temp_reader(client) == case.new_temp
        await hass.async_block_till_done()


async def test_set_temperature_mode_heat_cool(
    hass: HomeAssistant, mock_evolution_entry: MockConfigEntry
) -> None:
    """Test that changing the setpoint in HEAT_COOL mode works."""
    client = mock_evolution_entry.runtime_data[(1, 1)]

    data = {"hvac_mode": HVACMode.HEAT_COOL}
    data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
    await hass.services.async_call(
        "climate", SERVICE_SET_HVAC_MODE, data, blocking=True
    )
    data = {"target_temp_low": 50, "target_temp_high": 90}
    data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
    await hass.services.async_call(
        "climate", SERVICE_SET_TEMPERATURE, data, blocking=True
    )
    state = hass.states.get("climate.system_1_zone_1")
    assert state.attributes["target_temp_low"] == 50
    assert state.attributes["target_temp_high"] == 90
    assert await client.read_cooling_setpoint() == 90
    assert await client.read_heating_setpoint() == 50
    assert await client.read_hvac_mode() == ("auto", False)

    # Change the setpoint, pausing reads to the device so that we
    # verify that changes are locally committed.
    await client.set_allow_reads(False)
    data = {"target_temp_low": 70, "target_temp_high": 80}
    data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
    await hass.services.async_call(
        "climate", SERVICE_SET_TEMPERATURE, data, blocking=False
    )
    await _wait_for_cond(
        lambda s=hass.states.get("climate.system_1_zone_1"): s.attributes[
            "target_temp_low"
        ]
        == 70
        and s.attributes["target_temp_high"] == 80
    )
    await client.set_allow_reads(True)
    await hass.async_block_till_done()


async def test_set_fan_mode(
    hass: HomeAssistant, mock_evolution_entry: MockConfigEntry
) -> None:
    """Test that setting fan mode works."""
    fan_modes = ["auto", "low", "med", "high"]
    client = mock_evolution_entry.runtime_data[(1, 1)]
    for mode in fan_modes:
        # Change the fan mode, pausing reads to the device so that we
        # verify that changes are locally committed.
        await client.set_allow_reads(False)
        data = {ATTR_FAN_MODE: mode}
        data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
        await hass.services.async_call(
            "climate", SERVICE_SET_FAN_MODE, data, blocking=False
        )
        await _wait_for_cond(
            lambda mode=mode,
            s=hass.states.get("climate.system_1_zone_1"): s.attributes[ATTR_FAN_MODE]
            == mode
        )
        await client.set_allow_reads(True)
        await hass.async_block_till_done()
        assert await client.read_fan_mode() == mode


async def test_hvac_action(
    hass: HomeAssistant, mock_evolution_entry: MockConfigEntry
) -> None:
    """Test that we can read the current HVAC action."""
    client = mock_evolution_entry.runtime_data[(1, 1)]

    # Initial state should be no action.
    assert (
        hass.states.get("climate.system_1_zone_1").attributes[ATTR_HVAC_ACTION]
        == HVACAction.OFF
    )

    # Turn on the system and verify we see an action; we change the fan
    # mode to trigger the integration to re-read the device.
    await client.set_is_active(True)
    assert await client.read_hvac_mode() == ("COOL", True)
    data = {ATTR_FAN_MODE: "auto"}
    data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
    await hass.services.async_call(
        "climate", SERVICE_SET_FAN_MODE, data, blocking=False
    )
    await _wait_for_cond(
        lambda s=hass.states.get("climate.system_1_zone_1"): s.attributes[
            ATTR_HVAC_ACTION
        ]
        == HVACAction.COOLING
    )
