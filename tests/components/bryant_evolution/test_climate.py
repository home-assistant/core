"""Test the BryantEvolutionClient type."""

from contextlib import contextmanager
from datetime import timedelta
import itertools
import logging
from unittest.mock import AsyncMock, patch

from evolutionhttp import BryantEvolutionLocalClient
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.bryant_evolution.climate import SCAN_INTERVAL
from homeassistant.components.bryant_evolution.const import CONF_SYSTEM_ZONE, DOMAIN
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


@contextmanager
def disable_auto_entity_update():
    """Context manager to disable auto entity updates."""
    with patch(
        "homeassistant.helpers.entity.Entity.async_update_ha_state", return_value=None
    ) as patch_update:
        yield patch_update


async def trigger_polling(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger a polling event."""
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


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
    hass: HomeAssistant, mock_evolution_client_factory: AsyncMock
) -> None:
    """Test that setup throws ConfigEntryNotReady when the client is unavailable."""
    mock_evolution_client_factory.side_effect = FileNotFoundError("test error")
    mock_evolution_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_FILENAME: "test_setup_integration_prevented_by_unavailable_client",
            CONF_SYSTEM_ZONE: [(1, 1)],
        },
    )
    mock_evolution_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_evolution_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_evolution_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_integration_client_returns_none(
    hass: HomeAssistant, mock_evolution_client_factory: AsyncMock
) -> None:
    """Test that an unavailable client causes ConfigEntryNotReady."""
    mock_client = AsyncMock(spec=BryantEvolutionLocalClient)
    mock_evolution_client_factory.side_effect = None
    mock_evolution_client_factory.return_value = mock_client
    mock_client.read_fan_mode.return_value = None
    mock_client.read_current_temperature.return_value = None
    mock_client.read_hvac_mode.return_value = None
    mock_client.read_cooling_setpoint.return_value = None
    mock_client.read_zone_name.return_value = None
    mock_evolution_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_FILENAME: "/dev/ttyUSB0", CONF_SYSTEM_ZONE: [(1, 1)]},
    )
    mock_evolution_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_evolution_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_evolution_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_multiple_systems_zones(
    hass: HomeAssistant,
    mock_evolution_client_factory: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device with multiple systems and zones works."""
    szs = [(1, 1), (1, 2), (2, 3)]
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_evolution_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_FILENAME: "/dev/ttyUSB0", CONF_SYSTEM_ZONE: szs},
    )
    mock_evolution_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_evolution_entry.entry_id)
    await hass.async_block_till_done()

    # Set the temperature of each zone to its zone number so that we can
    # ensure we've created the right client for each zone.
    for sz, client in mock_evolution_entry.runtime_data.items():
        client.read_current_temperature.return_value = sz[1]
    await trigger_polling(hass, freezer)

    # Check that each system and zone has the expected temperature value to
    # verify that the initial setup flow worked as expected.
    for sz in szs:
        system = sz[0]
        zone = sz[1]
        state = hass.states.get(f"climate.system_{system}_zone_{zone}")
        assert state, hass.states.async_all()
        assert state.attributes["current_temperature"] == zone

    # Check that the created devices are wired to each other as expected.
    device_registry = dr.async_get(hass)

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


async def test_set_temperature_mode_cool(
    hass: HomeAssistant,
    mock_evolution_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setting the temperature in cool mode."""
    # Start with known initial conditions
    client = mock_evolution_entry.runtime_data[(1, 1)]
    client.read_hvac_mode.return_value = ("COOL", False)
    client.read_cooling_setpoint.return_value = 75
    await trigger_polling(hass, freezer)
    state = hass.states.get("climate.system_1_zone_1")
    assert state.attributes["temperature"] == 75, state.attributes

    # Make the call
    data = {"temperature": 70}
    data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
    with disable_auto_entity_update():
        await hass.services.async_call(
            "climate", SERVICE_SET_TEMPERATURE, data, blocking=True
        )

    # Verify effect.
    client.set_cooling_setpoint.assert_called_once_with(70)
    state = hass.states.get("climate.system_1_zone_1")
    assert state.attributes["temperature"] == 70


async def test_set_temperature_mode_heat(
    hass: HomeAssistant,
    mock_evolution_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setting the temperature in heat mode."""

    # Start with known initial conditions
    client = mock_evolution_entry.runtime_data[(1, 1)]
    client.read_hvac_mode.return_value = ("HEAT", False)
    client.read_heating_setpoint.return_value = 60
    await trigger_polling(hass, freezer)

    # Make the call
    data = {"temperature": 65}
    data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
    with disable_auto_entity_update():
        await hass.services.async_call(
            "climate", SERVICE_SET_TEMPERATURE, data, blocking=True
        )

    # Verify effect.
    client.set_heating_setpoint.assert_called_once_with(65)
    state = hass.states.get("climate.system_1_zone_1")
    assert state.attributes["temperature"] == 65, state.attributes


async def test_set_temperature_mode_heat_cool(
    hass: HomeAssistant,
    mock_evolution_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setting the temperature in heat_cool mode."""

    # Enter heat_cool with known setpoints
    mock_client = mock_evolution_entry.runtime_data[(1, 1)]
    mock_client.read_hvac_mode.return_value = ("AUTO", False)
    mock_client.read_cooling_setpoint.return_value = 90
    mock_client.read_heating_setpoint.return_value = 40
    await trigger_polling(hass, freezer)
    state = hass.states.get("climate.system_1_zone_1")
    assert state.state == "heat_cool"
    assert state.attributes["target_temp_low"] == 40
    assert state.attributes["target_temp_high"] == 90

    with disable_auto_entity_update():
        data = {"target_temp_low": 70, "target_temp_high": 80}
        data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
        await hass.services.async_call(
            "climate", SERVICE_SET_TEMPERATURE, data, blocking=True
        )
    state = hass.states.get("climate.system_1_zone_1")
    assert state.attributes["target_temp_low"] == 70, state.attributes
    assert state.attributes["target_temp_high"] == 80, state.attributes
    mock_client.set_cooling_setpoint.assert_called_once_with(80)
    mock_client.set_heating_setpoint.assert_called_once_with(70)


async def test_set_fan_mode(
    hass: HomeAssistant, mock_evolution_entry: MockConfigEntry
) -> None:
    """Test that setting fan mode works."""
    mock_client = mock_evolution_entry.runtime_data[(1, 1)]
    fan_modes = ["auto", "low", "med", "high"]
    for mode in fan_modes:
        # Change the fan mode, pausing reads to the device so that we
        # verify that changes are locally committed.
        data = {ATTR_FAN_MODE: mode}
        data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
        with disable_auto_entity_update():
            await hass.services.async_call(
                "climate", SERVICE_SET_FAN_MODE, data, blocking=True
            )
            await hass.async_block_till_done()
        assert (
            hass.states.get("climate.system_1_zone_1").attributes[ATTR_FAN_MODE] == mode
        )
        mock_client.set_fan_mode.assert_called_with(mode)


async def test_set_hvac_mode(
    hass: HomeAssistant, mock_evolution_entry: MockConfigEntry
) -> None:
    """Test that setting HVAC mode works."""
    mock_client = mock_evolution_entry.runtime_data[(1, 1)]
    hvac_modes = ["heat_cool", "heat", "cool", "off"]
    for mode in hvac_modes:
        # Change the mode, pausing reads to the device so that we
        # verify that changes are locally committed.
        data = {ATTR_HVAC_MODE: mode}
        data[ATTR_ENTITY_ID] = "climate.system_1_zone_1"
        with disable_auto_entity_update():
            await hass.services.async_call(
                "climate", SERVICE_SET_HVAC_MODE, data, blocking=True
            )
            await hass.async_block_till_done()
        evolution_mode = "auto" if mode == "heat_cool" else mode
        assert hass.states.get("climate.system_1_zone_1").state == evolution_mode
        mock_client.set_hvac_mode.assert_called_with(evolution_mode)


@pytest.mark.parametrize("curr_temp", [62, 70, 80])
async def test_read_hvac_action_heat_cool(
    hass: HomeAssistant,
    mock_evolution_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    curr_temp: int,
) -> None:
    """Test that we can read the current HVAC action in heat_cool mode."""
    htsp = 68
    clsp = 72

    mock_client = mock_evolution_entry.runtime_data[(1, 1)]
    mock_client.read_heating_setpoint.return_value = htsp
    mock_client.read_cooling_setpoint.return_value = clsp
    is_active = curr_temp < htsp or curr_temp > clsp
    mock_client.read_hvac_mode.return_value = ("auto", is_active)
    mock_client.read_current_temperature.return_value = curr_temp
    await trigger_polling(hass, freezer)
    expected_action = (
        HVACAction.HEATING
        if curr_temp < 68
        else HVACAction.COOLING
        if curr_temp > 72
        else HVACAction.OFF
    )
    state = hass.states.get("climate.system_1_zone_1")
    assert state.attributes[ATTR_HVAC_ACTION] == expected_action


@pytest.mark.parametrize(
    ("mode", "active"),
    itertools.product(("heat", "cool", "off"), (True, False)),
)
async def test_read_hvac_action(
    hass: HomeAssistant,
    mock_evolution_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mode: str,
    active: bool,
) -> None:
    """Test that we can read the current HVAC action."""
    # Initial state should be no action.
    assert (
        hass.states.get("climate.system_1_zone_1").attributes[ATTR_HVAC_ACTION]
        == HVACAction.OFF
    )
    action = (
        "off"
        if not active
        else {
            "heat": "heating",
            "cool": "cooling",
            "off": "off",
        }[mode]
    )
    # Turn perturb the system and verify we see an action.
    mock_client = mock_evolution_entry.runtime_data[(1, 1)]
    mock_client.read_heating_setpoint.return_value = 75  # Needed if mode == heat
    mock_client.read_hvac_mode.return_value = (mode, active)
    await trigger_polling(hass, freezer)
    assert (
        hass.states.get("climate.system_1_zone_1").attributes[ATTR_HVAC_ACTION]
        == action
    )
