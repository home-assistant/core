"""Define test fixtures for Enphase Envoy."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import jwt
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
from pyenphase.const import SupportedFeatures
from pyenphase.models.dry_contacts import EnvoyDryContactSettings, EnvoyDryContactStatus
from pyenphase.models.enpower import EnvoyEnpower
from pyenphase.models.meters import EnvoyMeterData
from pyenphase.models.tariff import EnvoyStorageSettings, EnvoyTariff
import pytest
from typing_extensions import AsyncGenerator

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    hass: HomeAssistant, config: dict[str, str], serial_number: str
) -> MockConfigEntry:
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
def config_fixture() -> dict[str, str]:
    """Define a config entry data fixture."""
    return {
        CONF_HOST: "1.1.1.1",
        CONF_NAME: "Envoy 1234",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


@pytest.fixture(name="mock_envoy")
async def mock_envoy_fixture(
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
    request: pytest.FixtureRequest,
) -> Generator[AsyncMock, None, None]:
    """Define a mocked Envoy fixture."""
    mock_envoy = Mock(spec=Envoy)
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
        # load the fixture
        _load_fixture(mock_envoy, request.param)

        # set the mock for the methods
        mock_envoy.serial_number = serial_number
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
        mock_envoy.update = AsyncMock(return_value=mock_envoy.data)
        yield mock_envoy


def _load_fixture(mock_envoy: Envoy, fixture_name: str) -> None:
    """Load envoy model from fixture."""

    json_fixture = load_json_object_fixture(f"{fixture_name}.json", DOMAIN)

    mock_envoy.firmware = json_fixture["firmware"]
    mock_envoy.part_number = json_fixture["part_number"]
    mock_envoy.envoy_model = json_fixture["envoy_model"]
    mock_envoy.supported_features = SupportedFeatures(
        json_fixture["supported_features"]
    )
    mock_envoy.phase_mode = json_fixture["phase_mode"]
    mock_envoy.phase_count = json_fixture["phase_count"]
    mock_envoy.active_phase_count = json_fixture["active_phase_count"]
    mock_envoy.ct_meter_count = json_fixture["ct_meter_count"]
    mock_envoy.consumption_meter_type = json_fixture["consumption_meter_type"]
    mock_envoy.production_meter_type = json_fixture["production_meter_type"]
    mock_envoy.storage_meter_type = json_fixture["storage_meter_type"]

    mock_envoy.data = EnvoyData()
    _load_json_2_production_data(mock_envoy.data, json_fixture)
    _load_json_2_meter_data(mock_envoy.data, json_fixture)
    _load_json_2_inverter_data(mock_envoy.data, json_fixture)
    _load_json_2_encharge_enpower_data(mock_envoy.data, json_fixture)
    _load_json_2_raw_data(mock_envoy.data, json_fixture)


def _load_json_2_production_data(mocked_data: EnvoyData, json_fixture) -> None:
    """Fill envoy production data from fixture."""
    if item := json_fixture["data"].get("system_consumption"):
        mocked_data.system_consumption = EnvoySystemConsumption(**item)
    if item := json_fixture["data"].get("system_production"):
        mocked_data.system_production = EnvoySystemProduction(**item)
    if item := json_fixture["data"].get("system_consumption_phases"):
        mocked_data.system_consumption_phases = {}
        for sub_item, item_data in item.items():
            mocked_data.system_consumption_phases[sub_item] = EnvoySystemConsumption(
                **item_data
            )
    if item := json_fixture["data"].get("system_production_phases"):
        mocked_data.system_production_phases = {}
        for sub_item, item_data in item.items():
            mocked_data.system_production_phases[sub_item] = EnvoySystemProduction(
                **item_data
            )


def _load_json_2_meter_data(mocked_data: EnvoyData, json_fixture) -> None:
    """Fill envoy meter data from fixture."""
    if item := json_fixture["data"].get("ctmeter_production"):
        mocked_data.ctmeter_production = EnvoyMeterData(**item)
    if item := json_fixture["data"].get("ctmeter_consumption"):
        mocked_data.ctmeter_consumption = EnvoyMeterData(**item)
    if item := json_fixture["data"].get("ctmeter_storage"):
        mocked_data.ctmeter_storage = EnvoyMeterData(**item)
    if item := json_fixture["data"].get("ctmeter_production_phases"):
        mocked_data.ctmeter_production_phases = {}
        for sub_item, item_data in item.items():
            mocked_data.ctmeter_production_phases[sub_item] = EnvoyMeterData(
                **item_data
            )
    if item := json_fixture["data"].get("ctmeter_consumption_phases"):
        mocked_data.ctmeter_consumption_phases = {}
        for sub_item, item_data in item.items():
            mocked_data.ctmeter_consumption_phases[sub_item] = EnvoyMeterData(
                **item_data
            )
    if item := json_fixture["data"].get("ctmeter_storage_phases"):
        mocked_data.ctmeter_storage_phases = {}
        for sub_item, item_data in item.items():
            mocked_data.ctmeter_storage_phases[sub_item] = EnvoyMeterData(**item_data)


def _load_json_2_inverter_data(mocked_data: EnvoyData, json_fixture) -> None:
    """Fill envoy inverter data from fixture."""
    if item := json_fixture["data"].get("inverters"):
        mocked_data.inverters = {}
        for sub_item, item_data in item.items():
            mocked_data.inverters[sub_item] = EnvoyInverter(**item_data)


def _load_json_2_encharge_enpower_data(mocked_data: EnvoyData, json_fixture) -> None:
    """Fill envoy encharge/enpower data from fixture."""
    if item := json_fixture["data"].get("encharge_inventory"):
        mocked_data.encharge_inventory = {}
        for sub_item, item_data in item.items():
            mocked_data.encharge_inventory[sub_item] = EnvoyEncharge(**item_data)
    if item := json_fixture["data"].get("enpower"):
        mocked_data.enpower = EnvoyEnpower(**item)
    if item := json_fixture["data"].get("encharge_aggregate"):
        mocked_data.encharge_aggregate = EnvoyEnchargeAggregate(**item)
    if item := json_fixture["data"].get("encharge_power"):
        mocked_data.encharge_power = {}
        for sub_item, item_data in item.items():
            mocked_data.encharge_power[sub_item] = EnvoyEnchargePower(**item_data)
    if item := json_fixture["data"].get("tariff"):
        mocked_data.tariff = EnvoyTariff(**item)
        mocked_data.tariff.storage_settings = EnvoyStorageSettings(
            **item["storage_settings"]
        )
    if item := json_fixture["data"].get("dry_contact_status"):
        mocked_data.dry_contact_status = {}
        for sub_item, item_data in item.items():
            mocked_data.dry_contact_status[sub_item] = EnvoyDryContactStatus(
                **item_data
            )
    if item := json_fixture["data"].get("dry_contact_settings"):
        mocked_data.dry_contact_settings = {}
        for sub_item, item_data in item.items():
            mocked_data.dry_contact_settings[sub_item] = EnvoyDryContactSettings(
                **item_data
            )


def _load_json_2_raw_data(mocked_data: EnvoyData, json_fixture) -> None:
    """Fill envoy raw data from fixture."""
    if item := json_fixture["data"].get("raw"):
        mocked_data.raw = item


@pytest.fixture(name="setup_enphase_envoy")
async def setup_enphase_envoy_fixture(hass: HomeAssistant, config, mock_envoy):
    """Define a fixture to set up Enphase Envoy."""
    assert await async_setup_component(hass, DOMAIN, config)


@pytest.fixture(name="mock_authenticate")
def mock_authenticate() -> AsyncMock:
    """Define a mocked Envoy.authenticate fixture."""
    return AsyncMock()


@pytest.fixture(name="mock_auth")
def mock_auth(serial_number: str) -> EnvoyTokenAuth:
    """Define a mocked EnvoyAuth fixture."""
    token = jwt.encode(
        payload={"name": "envoy", "exp": 1907837780}, key="secret", algorithm="HS256"
    )
    return EnvoyTokenAuth("127.0.0.1", token=token, envoy_serial=serial_number)


@pytest.fixture(name="mock_setup")
def mock_setup() -> AsyncMock:
    """Define a mocked Envoy.setup fixture."""
    return AsyncMock()


@pytest.fixture(name="serial_number")
def serial_number_fixture() -> str:
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


@pytest.fixture(name="entity_registry")
def get_entity_registry(hass: HomeAssistant):
    """Load entity registry."""
    return er.async_get(hass)
