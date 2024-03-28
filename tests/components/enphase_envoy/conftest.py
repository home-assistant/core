"""Define test fixtures for Enphase Envoy."""

from unittest.mock import AsyncMock, Mock, patch

from pyenphase import (
    Envoy,
    EnvoyData,
    EnvoyEncharge,
    EnvoyEnchargeAggregate,
    EnvoyEnchargePower,
    EnvoyInverter,
    EnvoySystemConsumption,
    EnvoySystemProduction,
    EnvoyTokenAuth,
)
from pyenphase.const import PhaseNames, SupportedFeatures
from pyenphase.models.dry_contacts import (
    DryContactAction,
    DryContactMode,
    DryContactStatus,
    DryContactType,
    EnvoyDryContactSettings,
    EnvoyDryContactStatus,
)
from pyenphase.models.enpower import EnvoyEnpower
from pyenphase.models.meters import (
    CtMeterStatus,
    CtState,
    CtStatusFlags,
    CtType,
    EnvoyMeterData,
    EnvoyPhaseMode,
)
from pyenphase.models.tariff import EnvoyStorageMode, EnvoyStorageSettings, EnvoyTariff
import pytest

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant, config, serial_number):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e72",
        title=f"Envoy {serial_number}" if serial_number else "Envoy",
        unique_id=serial_number,
        data=config,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return {
        CONF_HOST: "1.1.1.1",
        CONF_NAME: "Envoy 1234",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


@pytest.fixture(name="mock_envoy")
def mock_envoy_fixture(
    serial_number,
    mock_authenticate,
    mock_setup,
    mock_auth,
    mock_go_on_grid,
    mock_go_off_grid,
    mock_open_dry_contact,
    mock_close_dry_contact,
    mock_update_dry_contact,
    mock_disable_charge_from_grid,
    mock_enable_charge_from_grid,
    mock_set_reserve_soc,
    mock_set_storage_mode,
):
    """Define a mocked Envoy fixture."""
    mock_envoy = Mock(spec=Envoy)
    mock_envoy.serial_number = serial_number
    mock_envoy.firmware = "7.1.2"
    mock_envoy.part_number = "123456789"
    mock_envoy.envoy_model = "Envoy, phases: 3, phase mode: split, net-consumption CT, production CT, storage CT"
    mock_envoy.authenticate = mock_authenticate
    mock_envoy.go_off_grid = mock_go_off_grid
    mock_envoy.go_on_grid = mock_go_on_grid
    mock_envoy.open_dry_contact = mock_open_dry_contact
    mock_envoy.close_dry_contact = mock_close_dry_contact
    mock_envoy.disable_charge_from_grid = mock_disable_charge_from_grid
    mock_envoy.enable_charge_from_grid = mock_enable_charge_from_grid
    mock_envoy.update_dry_contact = mock_update_dry_contact
    mock_envoy.set_reserve_soc = mock_set_reserve_soc
    mock_envoy.set_storage_mode = mock_set_storage_mode

    mock_envoy.setup = mock_setup
    mock_envoy.auth = mock_auth
    mock_envoy.supported_features = SupportedFeatures(
        SupportedFeatures.INVERTERS
        | SupportedFeatures.PRODUCTION
        | SupportedFeatures.NET_CONSUMPTION
        | SupportedFeatures.METERING
        | SupportedFeatures.THREEPHASE
        | SupportedFeatures.CTMETERS
        | SupportedFeatures.ENCHARGE
        | SupportedFeatures.ENPOWER
    )
    mock_envoy.phase_mode = EnvoyPhaseMode.THREE
    mock_envoy.phase_count = 3
    mock_envoy.active_phase_count = 3
    mock_envoy.ct_meter_count = 2
    mock_envoy.consumption_meter_type = CtType.NET_CONSUMPTION
    mock_envoy.production_meter_type = CtType.PRODUCTION
    mock_envoy.storage_meter_type = CtType.STORAGE
    mock_envoy.data = EnvoyData(
        system_consumption=EnvoySystemConsumption(
            watt_hours_last_7_days=1234,
            watt_hours_lifetime=1234,
            watt_hours_today=1234,
            watts_now=1234,
        ),
        system_production=EnvoySystemProduction(
            watt_hours_last_7_days=1234,
            watt_hours_lifetime=1234,
            watt_hours_today=1234,
            watts_now=1234,
        ),
        system_consumption_phases={
            PhaseNames.PHASE_1: EnvoySystemConsumption(
                watt_hours_last_7_days=1321,
                watt_hours_lifetime=1322,
                watt_hours_today=1323,
                watts_now=1324,
            ),
            PhaseNames.PHASE_2: EnvoySystemConsumption(
                watt_hours_last_7_days=2321,
                watt_hours_lifetime=2322,
                watt_hours_today=2323,
                watts_now=2324,
            ),
            PhaseNames.PHASE_3: EnvoySystemConsumption(
                watt_hours_last_7_days=3321,
                watt_hours_lifetime=3322,
                watt_hours_today=3323,
                watts_now=3324,
            ),
        },
        system_production_phases={
            PhaseNames.PHASE_1: EnvoySystemProduction(
                watt_hours_last_7_days=1231,
                watt_hours_lifetime=1232,
                watt_hours_today=1233,
                watts_now=1234,
            ),
            PhaseNames.PHASE_2: EnvoySystemProduction(
                watt_hours_last_7_days=2231,
                watt_hours_lifetime=2232,
                watt_hours_today=2233,
                watts_now=2234,
            ),
            PhaseNames.PHASE_3: EnvoySystemProduction(
                watt_hours_last_7_days=3231,
                watt_hours_lifetime=3232,
                watt_hours_today=3233,
                watts_now=3234,
            ),
        },
        ctmeter_production=EnvoyMeterData(
            eid="100000010",
            timestamp=1708006110,
            energy_delivered=11234,
            energy_received=12345,
            active_power=100,
            power_factor=0.11,
            voltage=111,
            current=0.2,
            frequency=50.1,
            state=CtState.ENABLED,
            measurement_type=CtType.PRODUCTION,
            metering_status=CtMeterStatus.NORMAL,
            status_flags=[
                CtStatusFlags.PODUCTION_IMBALANCE,
                CtStatusFlags.POWER_ON_UNUSED_PHASE,
            ],
        ),
        ctmeter_consumption=EnvoyMeterData(
            eid="100000020",
            timestamp=1708006120,
            energy_delivered=21234,
            energy_received=22345,
            active_power=101,
            power_factor=0.21,
            voltage=112,
            current=0.3,
            frequency=50.2,
            state=CtState.ENABLED,
            measurement_type=CtType.NET_CONSUMPTION,
            metering_status=CtMeterStatus.NORMAL,
            status_flags=[],
        ),
        ctmeter_storage=EnvoyMeterData(
            eid="100000030",
            timestamp=1708006120,
            energy_delivered=31234,
            energy_received=32345,
            active_power=103,
            power_factor=0.23,
            voltage=113,
            current=0.4,
            frequency=50.3,
            state=CtState.ENABLED,
            measurement_type=CtType.STORAGE,
            metering_status=CtMeterStatus.NORMAL,
            status_flags=[],
        ),
        ctmeter_production_phases={
            PhaseNames.PHASE_1: EnvoyMeterData(
                eid="100000011",
                timestamp=1708006111,
                energy_delivered=112341,
                energy_received=123451,
                active_power=20,
                power_factor=0.12,
                voltage=111,
                current=0.2,
                frequency=50.1,
                state=CtState.ENABLED,
                measurement_type=CtType.PRODUCTION,
                metering_status=CtMeterStatus.NORMAL,
                status_flags=[CtStatusFlags.PODUCTION_IMBALANCE],
            ),
            PhaseNames.PHASE_2: EnvoyMeterData(
                eid="100000012",
                timestamp=1708006112,
                energy_delivered=112342,
                energy_received=123452,
                active_power=30,
                power_factor=0.13,
                voltage=111,
                current=0.2,
                frequency=50.1,
                state=CtState.ENABLED,
                measurement_type=CtType.PRODUCTION,
                metering_status=CtMeterStatus.NORMAL,
                status_flags=[CtStatusFlags.POWER_ON_UNUSED_PHASE],
            ),
            PhaseNames.PHASE_3: EnvoyMeterData(
                eid="100000013",
                timestamp=1708006113,
                energy_delivered=112343,
                energy_received=123453,
                active_power=50,
                power_factor=0.14,
                voltage=111,
                current=0.2,
                frequency=50.1,
                state=CtState.ENABLED,
                measurement_type=CtType.PRODUCTION,
                metering_status=CtMeterStatus.NORMAL,
                status_flags=[],
            ),
        },
        ctmeter_consumption_phases={
            PhaseNames.PHASE_1: EnvoyMeterData(
                eid="100000021",
                timestamp=1708006121,
                energy_delivered=212341,
                energy_received=223451,
                active_power=21,
                power_factor=0.22,
                voltage=112,
                current=0.3,
                frequency=50.2,
                state=CtState.ENABLED,
                measurement_type=CtType.NET_CONSUMPTION,
                metering_status=CtMeterStatus.NORMAL,
                status_flags=[],
            ),
            PhaseNames.PHASE_2: EnvoyMeterData(
                eid="100000022",
                timestamp=1708006122,
                energy_delivered=212342,
                energy_received=223452,
                active_power=31,
                power_factor=0.23,
                voltage=112,
                current=0.3,
                frequency=50.2,
                state=CtState.ENABLED,
                measurement_type=CtType.NET_CONSUMPTION,
                metering_status=CtMeterStatus.NORMAL,
                status_flags=[],
            ),
            PhaseNames.PHASE_3: EnvoyMeterData(
                eid="100000023",
                timestamp=1708006123,
                energy_delivered=212343,
                energy_received=223453,
                active_power=51,
                power_factor=0.24,
                voltage=112,
                current=0.3,
                frequency=50.2,
                state=CtState.ENABLED,
                measurement_type=CtType.NET_CONSUMPTION,
                metering_status=CtMeterStatus.NORMAL,
                status_flags=[],
            ),
        },
        ctmeter_storage_phases={
            PhaseNames.PHASE_1: EnvoyMeterData(
                eid="100000031",
                timestamp=1708006121,
                energy_delivered=312341,
                energy_received=323451,
                active_power=22,
                power_factor=0.32,
                voltage=113,
                current=0.4,
                frequency=50.3,
                state=CtState.ENABLED,
                measurement_type=CtType.STORAGE,
                metering_status=CtMeterStatus.NORMAL,
                status_flags=[],
            ),
            PhaseNames.PHASE_2: EnvoyMeterData(
                eid="100000032",
                timestamp=1708006122,
                energy_delivered=312342,
                energy_received=323452,
                active_power=33,
                power_factor=0.23,
                voltage=112,
                current=0.3,
                frequency=50.2,
                state=CtState.ENABLED,
                measurement_type=CtType.STORAGE,
                metering_status=CtMeterStatus.NORMAL,
                status_flags=[],
            ),
            PhaseNames.PHASE_3: EnvoyMeterData(
                eid="100000033",
                timestamp=1708006123,
                energy_delivered=312343,
                energy_received=323453,
                active_power=53,
                power_factor=0.24,
                voltage=112,
                current=0.3,
                frequency=50.2,
                state=CtState.ENABLED,
                measurement_type=CtType.STORAGE,
                metering_status=CtMeterStatus.NORMAL,
                status_flags=[],
            ),
        },
        inverters={
            "1": EnvoyInverter(
                serial_number="1",
                last_report_date=1,
                last_report_watts=1,
                max_report_watts=1,
            )
        },
        encharge_inventory={
            "123456": EnvoyEncharge(
                admin_state=6,
                admin_state_str="ENCHG_STATE_READY",
                bmu_firmware_version="2.1.34",
                comm_level_2_4_ghz=4,
                comm_level_sub_ghz=4,
                communicating=True,
                dc_switch_off=False,
                encharge_capacity=3500,
                encharge_revision=2,
                firmware_loaded_date=1695330323,
                firmware_version="2.6.5973_rel/22.11",
                installed_date=1695330323,
                last_report_date=1695769447,
                led_status=17,
                max_cell_temp=30,
                operating=True,
                part_number="830-01760-r37",
                percent_full=15,
                serial_number="123456",
                temperature=29,
                temperature_unit="C",
                zigbee_dongle_fw_version="100F",
            )
        },
        enpower=EnvoyEnpower(
            grid_mode="multimode-ongrid",
            admin_state=24,
            admin_state_str="ENPWR_STATE_OPER_CLOSED",
            comm_level_2_4_ghz=5,
            comm_level_sub_ghz=5,
            communicating=True,
            firmware_loaded_date=1695330323,
            firmware_version="1.2.2064_release/20.34",
            installed_date=1695330323,
            last_report_date=1695769447,
            mains_admin_state="closed",
            mains_oper_state="closed",
            operating=True,
            part_number="830-01760-r37",
            serial_number="654321",
            temperature=79,
            temperature_unit="F",
            zigbee_dongle_fw_version="1009",
        ),
        encharge_power={
            "123456": EnvoyEnchargePower(apparent_power_mva=0, real_power_mw=0, soc=15)
        },
        encharge_aggregate=EnvoyEnchargeAggregate(
            available_energy=525,
            backup_reserve=526,
            state_of_charge=15,
            reserve_state_of_charge=15,
            configured_reserve_state_of_charge=15,
            max_available_capacity=3500,
        ),
        tariff=EnvoyTariff(
            currency={"code": "EUR"},
            logger="mylogger",
            date="1695744220",
            storage_settings=EnvoyStorageSettings(
                mode=EnvoyStorageMode.SELF_CONSUMPTION,
                operation_mode_sub_type="",
                reserved_soc=15.0,
                very_low_soc=5,
                charge_from_grid=True,
                date="1695598084",
            ),
            single_rate={"rate": 0.0, "sell": 0.0},
            seasons=[
                {
                    "id": "season_1",
                    "start": "1/1",
                    "days": [
                        {
                            "id": "all_days",
                            "days": "Mon,Tue,Wed,Thu,Fri,Sat,Sun",
                            "must_charge_start": 444,
                            "must_charge_duration": 35,
                            "must_charge_mode": "CG",
                            "enable_discharge_to_grid": True,
                            "periods": [
                                {"id": "period_1", "start": 480, "rate": 0.1898},
                                {"id": "filler", "start": 1320, "rate": 0.1034},
                            ],
                        }
                    ],
                    "tiers": [],
                }
            ],
            seasons_sell=[],
        ),
        dry_contact_status={
            "NC1": EnvoyDryContactStatus(id="NC1", status=DryContactStatus.OPEN),
            "NC2": EnvoyDryContactStatus(id="NC2", status=DryContactStatus.CLOSED),
            "NC3": EnvoyDryContactStatus(id="NC3", status=DryContactStatus.OPEN),
        },
        dry_contact_settings={
            "NC1": EnvoyDryContactSettings(
                id="NC1",
                black_start=None,
                essential_end_time=None,
                essential_start_time=None,
                generator_action=DryContactAction.APPLY,
                grid_action=DryContactAction.SHED,
                load_name="",
                manual_override=None,
                micro_grid_action=DryContactAction.SCHEDULE,
                mode=DryContactMode.STATE_OF_CHARGE,
                override=False,
                priority=None,
                pv_serial_nb=[],
                soc_high=70.0,
                soc_low=30.0,
                type=DryContactType.NONE,
            ),
            "NC2": EnvoyDryContactSettings(
                id="NC2",
                black_start=None,
                essential_end_time=None,
                essential_start_time=None,
                generator_action=DryContactAction.SHED,
                grid_action=DryContactAction.APPLY,
                load_name="",
                manual_override=None,
                micro_grid_action=DryContactAction.NONE,
                mode=DryContactMode.MANUAL,
                override=False,
                priority=None,
                pv_serial_nb=[],
                soc_high=70.0,
                soc_low=30.0,
                type=DryContactType.NONE,
            ),
            "NC3": EnvoyDryContactSettings(
                id="NC3",
                black_start=None,
                essential_end_time=None,
                essential_start_time=None,
                generator_action=DryContactAction.NONE,
                grid_action=DryContactAction.APPLY,
                load_name="",
                manual_override=None,
                micro_grid_action=DryContactAction.SHED,
                mode=DryContactMode.MANUAL,
                override=False,
                priority=None,
                pv_serial_nb=[],
                soc_high=70.0,
                soc_low=30.0,
                type=DryContactType.NONE,
            ),
        },
        raw={"varies_by": "firmware_version"},
    )
    mock_envoy.update = AsyncMock(return_value=mock_envoy.data)
    return mock_envoy


@pytest.fixture(name="setup_enphase_envoy")
async def setup_enphase_envoy_fixture(hass, config, mock_envoy):
    """Define a fixture to set up Enphase Envoy."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=mock_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=mock_envoy,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="mock_authenticate")
def mock_authenticate():
    """Define a mocked Envoy.authenticate fixture."""
    return AsyncMock()


@pytest.fixture(name="mock_auth")
def mock_auth(serial_number):
    """Define a mocked EnvoyAuth fixture."""
    return EnvoyTokenAuth("127.0.0.1", token="abc", envoy_serial=serial_number)


@pytest.fixture(name="mock_setup")
def mock_setup():
    """Define a mocked Envoy.setup fixture."""
    return AsyncMock()


@pytest.fixture(name="serial_number")
def serial_number_fixture():
    """Define a serial number fixture."""
    return "1234"


@pytest.fixture(name="mock_go_on_grid")
def go_on_grid_fixture():
    """Define a go_on_grid fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_go_off_grid")
def go_off_grid_fixture():
    """Define a go_off_grid fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_update_dry_contact")
def update_dry_contact_fixture():
    """Define a update_dry_contact fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_open_dry_contact")
def open_dry_contact_fixture():
    """Define a gopen dry contact fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_close_dry_contact")
def close_dry_contact_fixture():
    """Define a close dry contact fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_enable_charge_from_grid")
def enable_charge_from_grid_fixture():
    """Define a enable charge from grid fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_disable_charge_from_grid")
def disable_charge_from_grid_fixture():
    """Define a disable charge from grid fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_set_storage_mode")
def set_storage_mode_fixture():
    """Define a update_dry_contact fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_set_reserve_soc")
def set_reserve_soc_fixture():
    """Define a update_dry_contact fixture."""
    return AsyncMock(return_value="[]")
