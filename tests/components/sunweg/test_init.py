"""Tests for the Sun WEG init."""

from datetime import datetime
import json
from unittest.mock import MagicMock, patch

import pytest
from sunweg.api import APIHelper
from sunweg.device import MPPT, Inverter, Phase, String
from sunweg.plant import Plant

from homeassistant.components.sunweg import SunWEGData
from homeassistant.components.sunweg.const import DOMAIN
from homeassistant.components.sunweg.device_type import DeviceType
from homeassistant.components.sunweg.sensor_types.sensor_entity_description import (
    SunWEGSensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import SUNWEG_MOCK_ENTRY


@pytest.fixture
def string_fixture() -> String:
    """Define String fixture."""
    return String("STR1", 450.3, 23.4, 0)


@pytest.fixture
def mppt_fixture(string_fixture) -> MPPT:
    """Define MPPT fixture."""
    mppt = MPPT("mppt")
    mppt.strings.append(string_fixture)
    return mppt


@pytest.fixture
def phase_fixture() -> Phase:
    """Define Phase fixture."""
    return Phase("PhaseA", 120.0, 3.2, 0, 0)


@pytest.fixture
def inverter_fixture(phase_fixture, mppt_fixture) -> Inverter:
    """Define inverter fixture."""
    inverter = Inverter(
        21255,
        "INVERSOR01",
        "J63T233018RE074",
        23.2,
        0.0,
        0.0,
        "MWh",
        0,
        "kWh",
        0.0,
        1,
        0,
        "kW",
    )
    inverter.phases.append(phase_fixture)
    inverter.mppts.append(mppt_fixture)
    return inverter


@pytest.fixture
def plant_fixture(inverter_fixture) -> Plant:
    """Define Plant fixture."""
    plant = Plant(
        123456,
        "Plant #123",
        29.5,
        0.5,
        0,
        12.786912,
        24.0,
        "kWh",
        332.2,
        0.012296,
        datetime(2023, 2, 16, 14, 22, 37),
    )
    plant.inverters.append(inverter_fixture)
    return plant


async def test_methods(hass: HomeAssistant, plant_fixture, inverter_fixture) -> None:
    """Test methods."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)

    with patch.object(APIHelper, "authenticate", return_value=True), patch.object(
        APIHelper, "listPlants", return_value=[plant_fixture]
    ), patch.object(APIHelper, "plant", return_value=plant_fixture), patch.object(
        APIHelper, "inverter", return_value=inverter_fixture
    ), patch.object(APIHelper, "complete_inverter"):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(mock_entry.entry_id)


async def test_setup_wrongpass(hass: HomeAssistant) -> None:
    """Test setup with wrong pass."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    with patch.object(APIHelper, "authenticate", return_value=False):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()


async def test_sunwegdata_update_exception() -> None:
    """Test SunWEGData exception on update."""
    api = MagicMock()
    api.plant = MagicMock(side_effect=json.decoder.JSONDecodeError("Message", "Doc", 1))
    data = SunWEGData(api, 0)
    data.update()
    assert data.data is None


async def test_sunwegdata_update_success(plant_fixture) -> None:
    """Test SunWEGData success on update."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    data = SunWEGData(api, 0)
    data.update()
    assert data.data.id == plant_fixture.id
    assert data.data.name == plant_fixture.name
    assert data.data.kwh_per_kwp == plant_fixture.kwh_per_kwp
    assert data.data.last_update == plant_fixture.last_update
    assert data.data.performance_rate == plant_fixture.performance_rate
    assert data.data.saving == plant_fixture.saving
    assert len(data.data.inverters) == 1


async def test_sunwegdata_get_api_value_none(plant_fixture) -> None:
    """Test SunWEGData none return on get_api_value."""
    api = MagicMock()
    data = SunWEGData(api, 123456)
    data.data = plant_fixture
    assert data.get_api_value("variable", DeviceType.INVERTER, 0, "deep_name") is None
    assert data.get_api_value("variable", DeviceType.STRING, 21255, "deep_name") is None


async def test_sunwegdata_get_data_drop_threshold() -> None:
    """Test SunWEGData get_data with drop threshold."""
    api = MagicMock()
    data = SunWEGData(api, 123456)
    data.get_api_value = MagicMock()
    entity_description = SunWEGSensorEntityDescription(
        api_variable_key="variable", key="key"
    )
    entity_description.previous_value_drop_threshold = 0.1
    data.get_api_value.return_value = 3.0
    assert (
        data.get_data(
            entity_description=entity_description, device_type=DeviceType.TOTAL
        )
        == 3.0
    )
    data.get_api_value.return_value = 2.91
    assert (
        data.get_data(
            entity_description=entity_description, device_type=DeviceType.TOTAL
        )
        == 3.0
    )
    data.get_api_value.return_value = 2.8
    assert (
        data.get_data(
            entity_description=entity_description, device_type=DeviceType.TOTAL
        )
        == 2.8
    )


async def test_sunwegdata_get_data_never_reset() -> None:
    """Test SunWEGData get_data with never reset."""
    api = MagicMock()
    data = SunWEGData(api, 123456)
    data.get_api_value = MagicMock()
    entity_description = SunWEGSensorEntityDescription(
        api_variable_key="variable", key="key"
    )
    entity_description.never_resets = True
    data.get_api_value.return_value = 3.0
    assert (
        data.get_data(
            entity_description=entity_description, device_type=DeviceType.TOTAL
        )
        == 3.0
    )
    data.get_api_value.return_value = 0
    assert (
        data.get_data(
            entity_description=entity_description, device_type=DeviceType.TOTAL
        )
        == 3.0
    )
    data.get_api_value.return_value = 2.8
    assert (
        data.get_data(
            entity_description=entity_description, device_type=DeviceType.TOTAL
        )
        == 2.8
    )
