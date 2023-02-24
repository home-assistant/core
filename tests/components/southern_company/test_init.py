"""Test Southern Company setup."""

from unittest.mock import patch

from southern_company_api.exceptions import (
    CantReachSouthernCompany,
    InvalidLogin,
    NoJwtTokenFound,
    NoRequestTokenFound,
    NoScTokenFound,
)

from homeassistant.components.recorder.core import Recorder
from homeassistant.components.southern_company import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import async_init_integration, create_entry


async def test_unload_entry(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    entry = await async_init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_setup_entry_cant_reach_southern_company(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Ensures Southern Company being down retries setup."""
    entry = create_entry(hass)
    with patch(
        "homeassistant.components.southern_company.SouthernCompanyAPI.authenticate",
        side_effect=CantReachSouthernCompany,
    ):
        await hass.config_entries.async_forward_entry_setup(entry, DOMAIN)
        assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_entry_no_token_found(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Ensures no token found causes entry to retry."""
    entry = create_entry(hass)
    with patch(
        "homeassistant.components.southern_company.SouthernCompanyAPI.authenticate",
        side_effect=NoRequestTokenFound,
    ):
        await hass.config_entries.async_forward_entry_setup(entry, DOMAIN)
        assert entry.state == ConfigEntryState.SETUP_RETRY
    entry = create_entry(hass)
    assert entry.state == ConfigEntryState.NOT_LOADED
    with patch(
        "homeassistant.components.southern_company.SouthernCompanyAPI.authenticate",
        side_effect=NoScTokenFound,
    ):
        await hass.config_entries.async_forward_entry_setup(entry, DOMAIN)
        assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_entry_account_error(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Ensures that if we have an error while trying to get accounts, config entry retries."""
    with patch(
        "homeassistant.components.southern_company.SouthernCompanyAPI.authenticate"
    ):
        entry = create_entry(hass)
        with patch(
            "homeassistant.components.southern_company.SouthernCompanyAPI.get_accounts",
            side_effect=NoJwtTokenFound,
        ):
            await hass.config_entries.async_forward_entry_setup(entry, DOMAIN)
            assert entry.state == ConfigEntryState.SETUP_RETRY
        entry = create_entry(hass)
        assert entry.state == ConfigEntryState.NOT_LOADED
        with patch(
            "homeassistant.components.southern_company.SouthernCompanyAPI.get_accounts",
            side_effect=NoScTokenFound,
        ):
            await hass.config_entries.async_forward_entry_setup(entry, DOMAIN)
            assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_entry_invalid_login(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Ensures Config setup is error if login is wrong."""
    entry = create_entry(hass)
    with patch(
        "homeassistant.components.southern_company.SouthernCompanyAPI.authenticate",
        side_effect=InvalidLogin,
    ):
        await hass.config_entries.async_forward_entry_setup(entry, DOMAIN)
        assert entry.state == ConfigEntryState.SETUP_ERROR
