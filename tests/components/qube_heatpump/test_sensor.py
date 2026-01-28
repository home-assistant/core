"""Tests for the Qube Heat Pump sensor platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from python_qube_heatpump.models import QubeState

from homeassistant.components.qube_heatpump.const import CONF_HOST, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_qube_state_for_tests() -> QubeState:
    """Return a mock QubeState object for sensor tests."""
    state = QubeState()
    state.temp_supply = 45.0
    state.temp_return = 40.0
    state.temp_outside = 10.0
    state.temp_source_in = 8.0
    state.temp_source_out = 12.0
    state.temp_room = 21.0
    state.temp_dhw = 50.0
    state.power_thermic = 5000.0
    state.power_electric = 1200.0
    state.energy_total_electric = 123.456
    state.energy_total_thermic = 500.0
    state.cop_calc = 4.2
    state.compressor_speed = 3000.0
    state.flow_rate = 15.5
    state.setpoint_room_heat_day = 21.0
    state.setpoint_room_heat_night = 18.0
    state.setpoint_room_cool_day = 25.0
    state.setpoint_room_cool_night = 23.0
    state.setpoint_dhw = 55.0
    state.status_code = 1
    return state


@pytest.fixture
def sensor_mock_client(mock_qube_state_for_tests: QubeState) -> MagicMock:
    """Create a mock client for sensor tests."""
    client = MagicMock()
    client.host = "1.2.3.4"
    client.port = 502
    client.unit = 1
    client.connect = AsyncMock(return_value=True)
    client.is_connected = True
    client.close = AsyncMock(return_value=None)
    client.get_all_data = AsyncMock(return_value=mock_qube_state_for_tests)
    return client


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_qube_state_for_tests: QubeState,
    sensor_mock_client: MagicMock,
) -> None:
    """Test sensors are created during setup."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=sensor_mock_client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert entity state via core state machine
        states = hass.states.async_all()
        sensor_states = [s for s in states if s.entity_id.startswith("sensor.")]
        # Should have sensors
        assert len(sensor_states) >= 10


async def test_temperature_sensors(
    hass: HomeAssistant,
    mock_qube_state_for_tests: QubeState,
    sensor_mock_client: MagicMock,
) -> None:
    """Test temperature sensor values."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=sensor_mock_client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert entity state via core state machine
        states = hass.states.async_all()
        supply_sensors = [
            s for s in states if "aanvoertemperatuur" in s.entity_id.lower()
        ]
        assert len(supply_sensors) > 0
        assert float(supply_sensors[0].state) == 45.0


async def test_power_sensors(
    hass: HomeAssistant,
    mock_qube_state_for_tests: QubeState,
    sensor_mock_client: MagicMock,
) -> None:
    """Test power sensor values."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=sensor_mock_client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert entity state via core state machine
        states = hass.states.async_all()
        power_sensors = [s for s in states if "actueel_vermogen" in s.entity_id.lower()]
        assert len(power_sensors) > 0
        assert float(power_sensors[0].state) == 5000.0


async def test_computed_status_sensor(
    hass: HomeAssistant,
    mock_qube_state_for_tests: QubeState,
    sensor_mock_client: MagicMock,
) -> None:
    """Test computed status sensor."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=sensor_mock_client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert entity state via core state machine
        states = hass.states.async_all()
        status_sensors = [s for s in states if "status" in s.entity_id.lower()]
        assert len(status_sensors) > 0
        assert status_sensors[0].state == "1"


async def test_device_info(
    hass: HomeAssistant,
    mock_qube_state_for_tests: QubeState,
    sensor_mock_client: MagicMock,
) -> None:
    """Test device info is set correctly."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=sensor_mock_client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert DeviceEntry state via device registry
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, "1.2.3.4:1")})

        assert device is not None
        assert device.manufacturer == "Qube"
        assert device.model == "Heatpump"


async def test_cop_sensor(
    hass: HomeAssistant,
    mock_qube_state_for_tests: QubeState,
    sensor_mock_client: MagicMock,
) -> None:
    """Test COP sensor."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=sensor_mock_client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert entity state via core state machine
        states = hass.states.async_all()
        cop_sensors = [s for s in states if "cop" in s.entity_id.lower()]
        assert len(cop_sensors) > 0
        assert float(cop_sensors[0].state) == 4.2


async def test_flow_rate_sensor(
    hass: HomeAssistant,
    mock_qube_state_for_tests: QubeState,
    sensor_mock_client: MagicMock,
) -> None:
    """Test flow rate sensor."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=sensor_mock_client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert entity state via core state machine
        states = hass.states.async_all()
        flow_sensors = [s for s in states if "flow" in s.entity_id.lower()]
        assert len(flow_sensors) > 0
        assert float(flow_sensors[0].state) == 15.5


async def test_sensor_with_none_status_code(hass: HomeAssistant) -> None:
    """Test sensor handles None status code gracefully."""
    state = QubeState()
    state.temp_supply = 45.0
    state.energy_total_electric = 123.0
    state.status_code = None

    client = MagicMock()
    client.host = "1.2.3.4"
    client.port = 502
    client.unit = 1
    client.connect = AsyncMock(return_value=True)
    client.is_connected = True
    client.close = AsyncMock(return_value=None)
    client.get_all_data = AsyncMock(return_value=state)

    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert entity state via core state machine
        states = hass.states.async_all()
        assert len(states) > 0


async def test_standby_sensors(
    hass: HomeAssistant,
    mock_qube_state_for_tests: QubeState,
    sensor_mock_client: MagicMock,
) -> None:
    """Test standby power and energy sensors exist."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=sensor_mock_client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert entity state via core state machine
        states = hass.states.async_all()
        standby_power = [s for s in states if "standby_power" in s.entity_id.lower()]
        standby_energy = [s for s in states if "standby_energy" in s.entity_id.lower()]

        assert len(standby_power) > 0
        assert len(standby_energy) > 0


async def test_total_energy_sensor_with_none_data(hass: HomeAssistant) -> None:
    """Test total energy sensor handles None data."""
    state = QubeState()
    state.temp_supply = 45.0
    state.energy_total_electric = None
    state.status_code = 1

    client = MagicMock()
    client.host = "1.2.3.4"
    client.port = 502
    client.unit = 1
    client.connect = AsyncMock(return_value=True)
    client.is_connected = True
    client.close = AsyncMock(return_value=None)
    client.get_all_data = AsyncMock(return_value=state)

    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert entity state via core state machine
        states = hass.states.async_all()
        assert len(states) > 0


async def test_sensor_coordinator_refresh_updates_values(
    hass: HomeAssistant,
    mock_qube_state_for_tests: QubeState,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that coordinator refresh updates sensor values."""
    client = MagicMock()
    client.host = "1.2.3.4"
    client.port = 502
    client.unit = 1
    client.connect = AsyncMock(return_value=True)
    client.is_connected = True
    client.close = AsyncMock(return_value=None)
    client.get_all_data = AsyncMock(return_value=mock_qube_state_for_tests)

    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert initial entity state via core state machine
        states = hass.states.async_all()
        supply_sensors = [
            s for s in states if "aanvoertemperatuur" in s.entity_id.lower()
        ]
        assert float(supply_sensors[0].state) == 45.0

        # Update mock data for next fetch
        new_state = QubeState()
        new_state.temp_supply = 50.0
        new_state.status_code = 1
        client.get_all_data.return_value = new_state

        # Trigger coordinator refresh via time advancement
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Assert updated entity state via core state machine
        states = hass.states.async_all()
        supply_sensors = [
            s for s in states if "aanvoertemperatuur" in s.entity_id.lower()
        ]
        assert float(supply_sensors[0].state) == 50.0
