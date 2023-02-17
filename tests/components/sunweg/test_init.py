"""Tests for the Sun WEG init."""

from unittest.mock import patch

from sunweg.plant import Plant

from homeassistant.components.sunweg.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    SUNWEG_INVERTER_RESPONSE,
    SUNWEG_LOGIN_RESPONSE,
    SUNWEG_MOCK_ENTRY,
    SUNWEG_MPPT_RESPONSE,
    SUNWEG_PHASE_RESPONSE,
    SUNWEG_PLANT_LIST_RESPONSE,
    SUNWEG_STRING_RESPONSE,
)


async def test_methods(hass: HomeAssistant) -> None:
    """Test methods."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    mppt = SUNWEG_MPPT_RESPONSE
    mppt.strings = [SUNWEG_STRING_RESPONSE]
    inverter = SUNWEG_INVERTER_RESPONSE
    inverter.phases = [SUNWEG_PHASE_RESPONSE]
    inverter.mppts = [mppt]
    plant: Plant = SUNWEG_PLANT_LIST_RESPONSE[0]
    plant.inverters = [inverter]

    with patch(
        "sunweg.api.APIHelper.authenticate", return_value=SUNWEG_LOGIN_RESPONSE
    ), patch("sunweg.api.APIHelper.listPlants", return_value=[plant]), patch(
        "sunweg.api.APIHelper.plant", return_value=plant
    ), patch(
        "sunweg.api.APIHelper.listPlants", return_value=[plant]
    ), patch(
        "sunweg.api.APIHelper.inverter", return_value=inverter
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry)
        await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(mock_entry.entry_id)


async def test_setup_wrongpass(hass: HomeAssistant) -> None:
    """Test setup with wrong pass."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    with patch("sunweg.api.APIHelper.authenticate", return_value=False):
        assert await async_setup_component(hass, DOMAIN, mock_entry)
        await hass.async_block_till_done()
