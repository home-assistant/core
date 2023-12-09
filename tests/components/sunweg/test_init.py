"""Tests for the Sun WEG init."""

from copy import deepcopy
import json
from unittest.mock import MagicMock, patch

from sunweg.api import APIHelper
from sunweg.device import MPPT, Inverter
from sunweg.plant import Plant

from homeassistant.components.sunweg import SunWEGData
from homeassistant.components.sunweg.const import DOMAIN
from homeassistant.components.sunweg.sensor_types.sensor_entity_description import (
    SunWEGSensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    SUNWEG_INVERTER_RESPONSE,
    SUNWEG_LOGIN_RESPONSE,
    SUNWEG_MOCK_ENTRY,
    SUNWEG_MPPT_RESPONSE,
    SUNWEG_PHASE_RESPONSE,
    SUNWEG_PLANT_RESPONSE,
    SUNWEG_STRING_RESPONSE,
)


async def test_methods(hass: HomeAssistant) -> None:
    """Test methods."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    mppt: MPPT = deepcopy(SUNWEG_MPPT_RESPONSE)
    mppt.strings.append(SUNWEG_STRING_RESPONSE)
    inverter: Inverter = deepcopy(SUNWEG_INVERTER_RESPONSE)
    inverter.phases.append(SUNWEG_PHASE_RESPONSE)
    inverter.mppts.append(mppt)
    plant: Plant = deepcopy(SUNWEG_PLANT_RESPONSE)
    plant.inverters.append(inverter)

    with patch.object(
        APIHelper, "authenticate", return_value=SUNWEG_LOGIN_RESPONSE
    ), patch.object(APIHelper, "listPlants", return_value=[plant]), patch.object(
        APIHelper, "plant", return_value=plant
    ), patch.object(APIHelper, "inverter", return_value=inverter), patch.object(
        APIHelper, "complete_inverter"
    ):
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


async def test_sunwegdata_update_success() -> None:
    """Test SunWEGData success on update."""
    inverter: Inverter = deepcopy(SUNWEG_INVERTER_RESPONSE)
    plant: Plant = deepcopy(SUNWEG_PLANT_RESPONSE)
    plant.inverters.append(inverter)
    api = MagicMock()
    api.plant = MagicMock(return_value=plant)
    api.complete_inverter = MagicMock()
    data = SunWEGData(api, 0)
    data.update()
    assert data.data.id == plant.id
    assert data.data.name == plant.name
    assert data.data.kwh_per_kwp == plant.kwh_per_kwp
    assert data.data.last_update == plant.last_update
    assert data.data.performance_rate == plant.performance_rate
    assert data.data.saving == plant.saving
    assert len(data.data.inverters) == 1


async def test_sunwegdata_get_api_value_none() -> None:
    """Test SunWEGData none return on get_api_value."""
    api = MagicMock()
    data = SunWEGData(api, 123456)
    data.data = deepcopy(SUNWEG_PLANT_RESPONSE)
    assert data.get_api_value("variable", "inverter", 0, "deep_name") is None
    data.data.inverters.append(deepcopy(SUNWEG_INVERTER_RESPONSE))
    assert data.get_api_value("variable", "invalid type", 21255, "deep_name") is None


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
        data.get_data(entity_description=entity_description, device_type="total") == 3.0
    )
    data.get_api_value.return_value = 2.91
    assert (
        data.get_data(entity_description=entity_description, device_type="total") == 3.0
    )
    data.get_api_value.return_value = 2.8
    assert (
        data.get_data(entity_description=entity_description, device_type="total") == 2.8
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
        data.get_data(entity_description=entity_description, device_type="total") == 3.0
    )
    data.get_api_value.return_value = 0
    assert (
        data.get_data(entity_description=entity_description, device_type="total") == 3.0
    )
    data.get_api_value.return_value = 2.8
    assert (
        data.get_data(entity_description=entity_description, device_type="total") == 2.8
    )
