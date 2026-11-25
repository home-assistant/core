"""Tests for the energieleser sensor platform."""

from unittest.mock import AsyncMock

from energieleser import (
    GasleserDevice,
    GasleserPulseDevice,
    WaermeleserDevice,
    WasserleserDevice,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import WAERMELESER_API_RESPONSE


async def _setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up the energieleser integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_energieleser_client"
)
async def test_stromleser_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test all stromleser sensors against a snapshot."""
    await _setup_integration(hass, mock_stromleser_config_entry)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_stromleser_config_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_gasleser_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_energieleser_client: AsyncMock,
    mock_gasleser_device: GasleserDevice,
    mock_gasleser_config_entry: MockConfigEntry,
) -> None:
    """Test all gasleser sensors against a snapshot."""
    mock_energieleser_client.get_device.return_value = mock_gasleser_device
    await _setup_integration(hass, mock_gasleser_config_entry)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_gasleser_config_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_gasleser_pulse_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_energieleser_client: AsyncMock,
    mock_gasleser_pulse_device: GasleserPulseDevice,
    mock_gasleser_pulse_config_entry: MockConfigEntry,
) -> None:
    """Test all gasleser.pulse sensors against a snapshot."""
    mock_energieleser_client.get_device.return_value = mock_gasleser_pulse_device
    await _setup_integration(hass, mock_gasleser_pulse_config_entry)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_gasleser_pulse_config_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_waermeleser_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_energieleser_client: AsyncMock,
    mock_waermeleser_device: WaermeleserDevice,
    mock_waermeleser_config_entry: MockConfigEntry,
) -> None:
    """Test all wärmeleser sensors against a snapshot."""
    mock_energieleser_client.get_device.return_value = mock_waermeleser_device
    await _setup_integration(hass, mock_waermeleser_config_entry)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_waermeleser_config_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_wasserleser_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_energieleser_client: AsyncMock,
    mock_wasserleser_device: WasserleserDevice,
    mock_wasserleser_config_entry: MockConfigEntry,
) -> None:
    """Test all wasserleser sensors against a snapshot."""
    mock_energieleser_client.get_device.return_value = mock_wasserleser_device
    await _setup_integration(hass, mock_wasserleser_config_entry)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_wasserleser_config_entry.entry_id
    )


@pytest.mark.parametrize(
    ("payload_key", "payload_value", "entity_id", "expected_state", "expected_unit"),
    [
        pytest.param(
            "total_energy_t1",
            "68006 kWh",
            "sensor.heat_0000000001_energy_tariff_1",
            "68006.0",
            "kWh",
            id="energy_kwh",
        ),
        pytest.param(
            "total_energy_t2",
            "245.8 GJ",
            "sensor.heat_0000000001_energy_tariff_2",
            "245.8",
            "GJ",
            id="energy_gj",
        ),
        pytest.param(
            "power",
            "2310 W",
            "sensor.heat_0000000001_power",
            "2310.0",
            "W",
            id="power_w",
        ),
        pytest.param(
            "total_volume",
            "3561.23 m3",
            "sensor.heat_0000000001_total_volume",
            "3561.23",
            "m³",
            id="volume_m3_alias",
        ),
        pytest.param(
            "volume_flow",
            "0.45 m3/h",
            "sensor.heat_0000000001_volume_flow",
            "0.45",
            "m³/h",
            id="volume_flow_m3_per_hour_alias",
        ),
        pytest.param(
            "total_energy_t3",
            "5.67 bananas",
            "sensor.heat_0000000001_energy_tariff_3",
            "5.67",
            "MWh",
            id="unknown_unit_falls_back",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_waermeleser_device_reported_units(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    mock_waermeleser_config_entry: MockConfigEntry,
    payload_key: str,
    payload_value: str,
    entity_id: str,
    expected_state: str,
    expected_unit: str,
) -> None:
    """Test wärmeleser sensors use the unit reported by the heat meter."""
    mock_energieleser_client.get_device.return_value = WaermeleserDevice.from_payload(
        {**WAERMELESER_API_RESPONSE, payload_key: payload_value}
    )
    await _setup_integration(hass, mock_waermeleser_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == expected_unit
