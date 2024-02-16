"""Tests for the Sun WEG init."""

import json
from unittest.mock import MagicMock, patch

from sunweg.api import APIHelper, SunWegApiError

from homeassistant.components.sunweg import SunWEGData
from homeassistant.components.sunweg.const import DOMAIN, DeviceType
from homeassistant.components.sunweg.sensor_types.sensor_entity_description import (
    SunWEGSensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import SUNWEG_MOCK_ENTRY


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


async def test_setup_error_500(hass: HomeAssistant) -> None:
    """Test setup with wrong pass."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    with patch.object(
        APIHelper, "authenticate", side_effect=SunWegApiError("Error 500")
    ):
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
        api_variable_key="variable", key="key", previous_value_drop_threshold=0.1
    )
    data.get_api_value.return_value = 3.0
    assert data.get_data(
        api_variable_key=entity_description.api_variable_key,
        api_variable_unit=entity_description.api_variable_unit,
        deep_name=None,
        device_type=DeviceType.TOTAL,
        inverter_id=0,
        name=entity_description.name,
        native_unit_of_measurement=entity_description.native_unit_of_measurement,
        never_resets=entity_description.never_resets,
        previous_value_drop_threshold=entity_description.previous_value_drop_threshold,
    ) == (3.0, None)
    data.get_api_value.return_value = 2.91
    assert data.get_data(
        api_variable_key=entity_description.api_variable_key,
        api_variable_unit=entity_description.api_variable_unit,
        deep_name=None,
        device_type=DeviceType.TOTAL,
        inverter_id=0,
        name=entity_description.name,
        native_unit_of_measurement=entity_description.native_unit_of_measurement,
        never_resets=entity_description.never_resets,
        previous_value_drop_threshold=entity_description.previous_value_drop_threshold,
    ) == (3.0, None)
    data.get_api_value.return_value = 2.8
    assert data.get_data(
        api_variable_key=entity_description.api_variable_key,
        api_variable_unit=entity_description.api_variable_unit,
        deep_name=None,
        device_type=DeviceType.TOTAL,
        inverter_id=0,
        name=entity_description.name,
        native_unit_of_measurement=entity_description.native_unit_of_measurement,
        never_resets=entity_description.never_resets,
        previous_value_drop_threshold=entity_description.previous_value_drop_threshold,
    ) == (2.8, None)


async def test_sunwegdata_get_data_never_reset() -> None:
    """Test SunWEGData get_data with never reset."""
    api = MagicMock()
    data = SunWEGData(api, 123456)
    data.get_api_value = MagicMock()
    entity_description = SunWEGSensorEntityDescription(
        api_variable_key="variable", key="key", never_resets=True
    )
    data.get_api_value.return_value = 3.0
    assert data.get_data(
        api_variable_key=entity_description.api_variable_key,
        api_variable_unit=entity_description.api_variable_unit,
        deep_name=None,
        device_type=DeviceType.TOTAL,
        inverter_id=0,
        name=entity_description.name,
        native_unit_of_measurement=entity_description.native_unit_of_measurement,
        never_resets=entity_description.never_resets,
        previous_value_drop_threshold=entity_description.previous_value_drop_threshold,
    ) == (3.0, None)
    data.get_api_value.return_value = 0
    assert data.get_data(
        api_variable_key=entity_description.api_variable_key,
        api_variable_unit=entity_description.api_variable_unit,
        deep_name=None,
        device_type=DeviceType.TOTAL,
        inverter_id=0,
        name=entity_description.name,
        native_unit_of_measurement=entity_description.native_unit_of_measurement,
        never_resets=entity_description.never_resets,
        previous_value_drop_threshold=entity_description.previous_value_drop_threshold,
    ) == (3.0, None)
    data.get_api_value.return_value = 2.8
    assert data.get_data(
        api_variable_key=entity_description.api_variable_key,
        api_variable_unit=entity_description.api_variable_unit,
        deep_name=None,
        device_type=DeviceType.TOTAL,
        inverter_id=0,
        name=entity_description.name,
        native_unit_of_measurement=entity_description.native_unit_of_measurement,
        never_resets=entity_description.never_resets,
        previous_value_drop_threshold=entity_description.previous_value_drop_threshold,
    ) == (2.8, None)
