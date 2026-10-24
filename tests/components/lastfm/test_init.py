"""Test LastFM component setup process."""

from unittest.mock import patch

from pylast import LastFMNetwork, WSError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.lastfm.const import (
    CONF_API_SECRET,
    CONF_SESSION_KEY,
    DOMAIN,
    ERROR_CODE_INVALID_SESSION_KEY,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from . import API_KEY, API_SECRET, SESSION_KEY, MockUser
from .conftest import ComponentSetup


async def test_load_unload_entry(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
) -> None:
    """Test load and unload entry."""
    await setup_integration(config_entry, default_user)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    state = hass.states.get("sensor.lastfm_testaccount1")
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.lastfm_testaccount1")
    assert not state


async def test_load_entry_with_session_key(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    default_user: MockUser,
) -> None:
    """Test the client is authenticated with a session key when configured."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            **config_entry.options,
            CONF_API_SECRET: API_SECRET,
            CONF_SESSION_KEY: SESSION_KEY,
        },
    )
    with (
        patch("pylast.User", return_value=default_user),
        patch(
            "homeassistant.components.lastfm.coordinator.LastFMNetwork",
            wraps=LastFMNetwork,
        ) as mock_network,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    mock_network.assert_called_once_with(
        api_key=API_KEY, api_secret=API_SECRET, session_key=SESSION_KEY
    )


@pytest.mark.parametrize(
    "user",
    [
        pytest.param(
            MockUser(
                thrown_error=WSError(
                    "network", ERROR_CODE_INVALID_SESSION_KEY, "Invalid session key"
                )
            ),
            id="user_data",
        ),
        pytest.param(
            MockUser(
                recent_tracks_error=WSError(
                    "network", ERROR_CODE_INVALID_SESSION_KEY, "Invalid session key"
                )
            ),
            id="recent_tracks",
        ),
    ],
)
async def test_invalid_session_key_starts_reauth(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
    user: MockUser,
) -> None:
    """Test an invalid session requests confirmation without starting authorization."""
    authenticated_config_entry.add_to_hass(hass)
    with (
        patch(
            "pylast.User",
            return_value=user,
        ),
        patch(
            "homeassistant.components.lastfm.config_flow.SessionKeyGenerator",
        ) as session_key_generator,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert len(flows) == 1
        assert flows[0]["step_id"] == "reauth_confirm"
        assert flows[0]["context"]["source"] == SOURCE_REAUTH
        session_key_generator.assert_not_called()

        result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        session_key_generator.assert_not_called()

        hass.config_entries.flow.async_abort(flows[0]["flow_id"])
        await hass.async_block_till_done()

    assert authenticated_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_setup_retry_when_no_user_data(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    not_found_user: MockUser,
) -> None:
    """Test setup is retried when no user data could be fetched."""
    await setup_integration(config_entry, not_found_user)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert config_entry.error_reason_translation_key == "update_failed"
    assert (
        config_entry.reason
        == "Could not retrieve data from Last.fm for any of the configured users"
    )
