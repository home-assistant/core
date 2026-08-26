"""Fixtures for Hot Spring integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from hotspring import (
    Blower,
    BrightnessLevel,
    CleanCycle,
    ConnectionStatus,
    Diagnostics,
    EnergySaving,
    FreshWaterIQ,
    Heater,
    HeatingMode,
    Jet,
    JetSpeed,
    LightColor,
    LightWheelMode,
    LightZone,
    LogoLight,
    Spa,
    SpaBrand,
    SpaFailureState,
    SpaInfo,
    SpaLock,
    TemperatureUnit,
    Versions,
    WaterCare,
)
from hotspring.models import SpaTestData
import pytest

from homeassistant.components.hotspring.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="AA:BB:CC:DD:EE:FF",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.hotspring.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def device_fixture() -> Spa:
    """Return the device fixture for a Hot Spring spa."""
    spa = MagicMock(spec=Spa)
    spa.info = SpaInfo(
        hostname="ConnectedSpa_DDEEFF",
        root_topic="mySpaAABBCCDDEEFF",
        sna_ready=True,
        brand=SpaBrand.HOTSPRING,
        brand_name="Hot Spring",
        collection="Highlife",
        model_name="Relay",
        brand_id="1",
        collection_id="1",
        model_id="1",
        volume=335,
    )
    spa.versions = Versions(
        control_box="3.0.0",
        control_panel="2.0.0",
        fwss="1.0.0",
        fwiq="",
        btxr="",
        cool_zone="",
        wifi_dongle="1.0.0",
        amp="",
        dosing="",
        logolight="",
    )
    spa.heater = Heater(
        is_on=True,
        heater_lock=False,
        heatpump_installed=False,
        heating_mode=HeatingMode.HEAT_SAVER,
        heater_current=5.0,
        heater_on_seconds=3600,
        set_temperature=104.0,
        current_temperature=102.0,
        temperature_unit=TemperatureUnit.FAHRENHEIT,
    )
    spa.water_care = WaterCare(
        cartridge_installed=True,
        ten_day_timer=0,
        one_twenty_day_timer=117,
        level=2,
        system_enabled=True,
        ace_mode="inactive",
        boost_active=False,
        salt_value=12,
    )
    spa.jets = [
        Jet(jet_id=1, speed=JetSpeed.OFF, is_enabled=True, on_seconds=0),
        Jet(jet_id=2, speed=JetSpeed.OFF, is_enabled=True, on_seconds=0),
    ]
    spa.blower = Blower(is_enabled=False, is_on=False)
    spa.light_zones = [
        LightZone(
            zone_id=1,
            is_enabled=True,
            is_on=False,
            color=LightColor.BLUE,
            light_wheel=LightWheelMode.OFF,
            intensity=0,
            loop_speed=0,
        ),
    ]
    spa.logo_light = LogoLight(brightness=BrightnessLevel.LEVEL_1)
    spa.clean_cycle = CleanCycle(is_enabled=False, vanishing_act=False)
    spa.spa_lock = SpaLock(is_locked=False)
    spa.freshwater_iq = FreshWaterIQ(
        conductivity=0,
        orp=0,
        chlorine=0.0,
        ph=7.2,
        sensor_life_percentage=100.0,
        installed=False,
    )
    spa.energy_savings = [
        EnergySaving(schedule_id=1, mode=0, start_hour=0, start_minute=0, duration=0),
    ]
    spa.connection_status = ConnectionStatus(spa_connected=True)
    spa.diagnostics = Diagnostics(
        spa_failure_state=SpaFailureState.OK,
        heater_error="0",
        power_frequency="60",
        pressure_switch_status="0",
        l1_n_volts=120.0,
        l2_n_volts=120.0,
        heater_volts=240.0,
        jet3_volts=0.0,
        jet1_jet2_blower_power="0",
        small_loads_power="0",
        heater_power="0",
        jet3_power="0",
    )
    spa.test_metrics = SpaTestData(
        heater_test_status="off",
        temp_offset=0.0,
        vsense_cal=0.0,
        jet1_jet2_blower_current=0.0,
        small_loads_current=0.0,
        heater_current=0.0,
        jet3_current=0.0,
    )
    return spa


@pytest.fixture
def mock_hotspring(device_fixture: Spa) -> Generator[MagicMock]:
    """Return a mocked HotSpring client."""
    with (
        patch(
            "homeassistant.components.hotspring.coordinator.HotSpring", autospec=True
        ) as hotspring_mock,
        patch(
            "homeassistant.components.hotspring.config_flow.HotSpring",
            new=hotspring_mock,
        ),
    ):
        client = hotspring_mock.return_value
        client.update.return_value = device_fixture
        client.spa = device_fixture
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> MockConfigEntry:
    """Set up the Hot Spring integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
