"""Tests for the Hot Spring sensor platform."""

from hotspring import Jet, JetSpeed, PowerMetrics, Spa, TemperatureUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

ENTITY_IDS = (
    "sensor.connectedspa_ddeeff_ph",
    "sensor.connectedspa_ddeeff_chlorine",
    "sensor.connectedspa_ddeeff_oxidation_reduction_potential",
    "sensor.connectedspa_ddeeff_sensor_life",
)

POWER_ENTITY_IDS = (
    "sensor.connectedspa_ddeeff_total_apparent_power",
    "sensor.connectedspa_ddeeff_heater_power",
    "sensor.connectedspa_ddeeff_small_loads_apparent_power",
    "sensor.connectedspa_ddeeff_jets_1_2_and_blower_apparent_power",
    "sensor.connectedspa_ddeeff_heater_current",
    "sensor.connectedspa_ddeeff_small_loads_current",
    "sensor.connectedspa_ddeeff_jets_1_2_and_blower_current",
)

JET3_POWER_ENTITY_IDS = (
    "sensor.connectedspa_ddeeff_jet_3_apparent_power",
    "sensor.connectedspa_ddeeff_jet_3_current",
)

ALL_POWER_ENTITY_IDS = (
    *POWER_ENTITY_IDS,
    *JET3_POWER_ENTITY_IDS,
)


def _enable_power_metrics(device_fixture: Spa) -> None:
    """Populate power metrics on the spa fixture."""
    device_fixture.power = PowerMetrics(
        supported=True,
        small_loads_power=110,
        jet1_jet2_blower_power=1450,
        heater_power=4000,
        jet3_power=900,
        jet1_jet2_blower_current=6,
        small_loads_current=1,
        heater_current=17,
        jet3_current=4,
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor platform state."""
    device_fixture.freshwater_iq.installed = True
    device_fixture.freshwater_iq.ph = 7.7
    device_fixture.freshwater_iq.chlorine = 23.1
    device_fixture.freshwater_iq.orp = 793
    device_fixture.freshwater_iq.sensor_life_percentage = 79.06
    device_fixture.jets[3] = Jet(
        jet_id=3, speed=JetSpeed.OFF, is_enabled=True, on_seconds=0
    )
    _enable_power_metrics(device_fixture)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_temperature_sensor_celsius(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the temperature sensor when the spa is configured in Celsius."""
    device_fixture.heater.temperature_unit = TemperatureUnit.CELSIUS
    device_fixture.heater.current_temperature = 38.5
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get("sensor.connectedspa_ddeeff_current_temperature") == snapshot


@pytest.mark.usefixtures("mock_hotspring")
async def test_freshwater_iq_sensors_absent_without_iq(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that no FreshWater IQ sensors are created when IQ is not installed."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    for entity_id in ENTITY_IDS:
        assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("mock_hotspring")
async def test_power_sensors_absent_when_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that no power or current sensors are created when unsupported."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    for entity_id in ALL_POWER_ENTITY_IDS:
        assert not entity_registry.async_is_registered(entity_id)


@pytest.mark.usefixtures("mock_hotspring")
@pytest.mark.parametrize(
    "extra_jets",
    [
        pytest.param({}, id="jet3_missing"),
        pytest.param(
            {3: Jet(jet_id=3, speed=JetSpeed.OFF, is_enabled=False, on_seconds=0)},
            id="jet3_disabled",
        ),
    ],
)
async def test_jet3_power_sensors_absent_without_jet3(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    entity_registry: er.EntityRegistry,
    extra_jets: dict[int, Jet],
) -> None:
    """Test Jet 3 power and current sensors are omitted when Jet 3 is unavailable."""
    device_fixture.jets.update(extra_jets)
    _enable_power_metrics(device_fixture)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    for entity_id in JET3_POWER_ENTITY_IDS:
        assert not entity_registry.async_is_registered(entity_id)
    for entity_id in POWER_ENTITY_IDS:
        assert entity_registry.async_is_registered(entity_id)
