"""Tests for the Sun WEG init."""

from unittest.mock import patch

from sunweg.api import LoginError, SunWegApiError

from homeassistant.components.sunweg.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import SUNWEG_MOCK_ENTRY


async def test_methods(hass: HomeAssistant) -> None:
    """Test methods."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.sunweg.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(mock_entry.entry_id)


async def test_setup_wrongpass(hass: HomeAssistant, api_fixture) -> None:
    """Test setup with wrong pass."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    api_fixture["authenticate"].return_value = False
    with (
        patch("homeassistant.components.sunweg.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_auth_failed(hass: HomeAssistant, api_fixture) -> None:
    """Test coordinator with expired token."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    api_fixture["listPlants"].side_effect = LoginError()
    with (
        patch("homeassistant.components.sunweg.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_error_500(hass: HomeAssistant, api_fixture) -> None:
    """Test coordinator with http error."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    api_fixture["listPlants"].side_effect = SunWegApiError("Error 500")
    with (
        patch("homeassistant.components.sunweg.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_empty_list(hass: HomeAssistant, api_fixture) -> None:
    """Test coordinator with empty list of plants."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    api_fixture["listPlants"].return_value = []
    with (
        patch("homeassistant.components.sunweg.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_plant_none(hass: HomeAssistant, api_fixture) -> None:
    """Test coordinator with plant not found by id."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    api_fixture["plant"].return_value = None
    with (
        patch("homeassistant.components.sunweg.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.SETUP_ERROR


async def test_reauth_started(hass: HomeAssistant, api_fixture) -> None:
    """Test reauth flow started."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    api_fixture["authenticate"].return_value = False

    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
