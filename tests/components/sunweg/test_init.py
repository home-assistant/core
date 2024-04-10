"""Tests for the Sun WEG init."""

from unittest.mock import patch

from sunweg.api import APIHelper, SunWegApiError

from homeassistant.components.sunweg.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import SUNWEG_MOCK_ENTRY


async def test_methods(hass: HomeAssistant, plant_fixture, inverter_fixture) -> None:
    """Test methods."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)

    with (
        patch.object(APIHelper, "authenticate", return_value=True),
        patch.object(APIHelper, "listPlants", return_value=[plant_fixture]),
        patch.object(APIHelper, "plant", return_value=plant_fixture),
        patch.object(APIHelper, "inverter", return_value=inverter_fixture),
        patch.object(APIHelper, "complete_inverter"),
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


async def test_setup_error_500(hass: HomeAssistant) -> None:
    """Test setup with wrong pass."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    with patch.object(
        APIHelper, "authenticate", side_effect=SunWegApiError("Error 500")
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()


async def test_reauth_started(hass: HomeAssistant) -> None:
    """Test reauth flow started."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    with patch.object(APIHelper, "authenticate", return_value=False):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
