"""Tests for the Qube Heat Pump sensor platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from python_qube_heatpump.models import QubeState

from homeassistant.components.qube_heatpump.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import get_entity_id_by_unique_id_suffix

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def sensor_mock_client(mock_qube_state: QubeState) -> MagicMock:
    """Create a mock client for sensor tests."""
    client = MagicMock()
    client.host = "1.2.3.4"
    client.port = 502
    client.unit = 1
    client.connect = AsyncMock(return_value=True)
    client.is_connected = True
    client.close = AsyncMock(return_value=None)
    client.get_all_data = AsyncMock(return_value=mock_qube_state)
    return client


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_qube_state: QubeState,
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
        # Should have sensors (19 regular + 1 status = 20)
        assert len(sensor_states) == 20


async def test_temperature_sensors(
    hass: HomeAssistant,
    mock_qube_state: QubeState,
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

        # Look up entity by unique_id via entity registry
        entity_id = get_entity_id_by_unique_id_suffix(
            hass, entry.unique_id, "temp_supply"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == 45.0


async def test_power_sensors(
    hass: HomeAssistant,
    mock_qube_state: QubeState,
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

        # Look up entity by unique_id via entity registry
        entity_id = get_entity_id_by_unique_id_suffix(
            hass, entry.unique_id, "power_thermic"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == 5000.0


async def test_computed_status_sensor(
    hass: HomeAssistant,
    mock_qube_state: QubeState,
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

        # Look up entity by unique_id via entity registry
        entity_id = get_entity_id_by_unique_id_suffix(
            hass, entry.unique_id, "status_heatpump"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        # status_code 1 maps to "alarm" in the implementation
        assert state.state == "alarm"


async def test_device_info(
    hass: HomeAssistant,
    mock_qube_state: QubeState,
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
        assert device.model == "Heat Pump"


async def test_cop_sensor(
    hass: HomeAssistant,
    mock_qube_state: QubeState,
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

        # Look up entity by unique_id via entity registry
        entity_id = get_entity_id_by_unique_id_suffix(hass, entry.unique_id, "cop_calc")
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == 4.2


async def test_flow_rate_sensor(
    hass: HomeAssistant,
    mock_qube_state: QubeState,
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

        # Look up entity by unique_id via entity registry
        entity_id = get_entity_id_by_unique_id_suffix(
            hass, entry.unique_id, "flow_rate"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == 15.5


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


async def test_energy_sensors(
    hass: HomeAssistant,
    mock_qube_state: QubeState,
    sensor_mock_client: MagicMock,
) -> None:
    """Test energy sensors exist and have correct values."""
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

        # Look up entities by unique_id via entity registry
        electric_entity_id = get_entity_id_by_unique_id_suffix(
            hass, entry.unique_id, "energy_total_electric"
        )
        thermic_entity_id = get_entity_id_by_unique_id_suffix(
            hass, entry.unique_id, "energy_total_thermic"
        )

        assert electric_entity_id is not None
        assert thermic_entity_id is not None

        electric_state = hass.states.get(electric_entity_id)
        thermic_state = hass.states.get(thermic_entity_id)

        assert electric_state is not None
        assert thermic_state is not None
        assert float(electric_state.state) == 123.456
        assert float(thermic_state.state) == 500.0


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
    mock_qube_state: QubeState,
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
    client.get_all_data = AsyncMock(return_value=mock_qube_state)

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

        # Look up entity by unique_id via entity registry
        entity_id = get_entity_id_by_unique_id_suffix(
            hass, entry.unique_id, "temp_supply"
        )
        assert entity_id is not None

        # Assert initial state
        state = hass.states.get(entity_id)
        assert float(state.state) == 45.0

        # Update mock data for next fetch
        new_state = QubeState()
        new_state.temp_supply = 50.0
        new_state.status_code = 1
        client.get_all_data.return_value = new_state

        # Trigger coordinator refresh via time advancement
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Assert updated state
        state = hass.states.get(entity_id)
        assert float(state.state) == 50.0
