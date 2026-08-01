"""Test LastFM component setup process."""

from unittest.mock import patch

from pylast import LastFMNetwork, WSError
import pytest

from homeassistant.components.lastfm.const import (
    CONF_API_SECRET,
    CONF_SESSION_KEY,
    DOMAIN,
    ERROR_CODE_INVALID_SESSION_KEY,
    ERROR_CODE_TOKEN_UNAUTHORIZED,
)
from homeassistant.components.lastfm.coordinator import LastFMDataUpdateCoordinator
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.setup import async_setup_component

from . import API_KEY, API_SECRET, SESSION_KEY, MockSessionKeyGenerator, MockUser
from .conftest import ComponentSetup

from tests.common import MockConfigEntry


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
async def test_invalid_session_key_raises_auth_failed(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
    user: MockUser,
) -> None:
    """Test an invalid stored session key raises an authentication failure."""
    coordinator = LastFMDataUpdateCoordinator(hass, authenticated_config_entry)
    with (
        patch("pylast.User", return_value=user),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._async_update_data()


async def test_invalid_session_key_starts_reauth(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
) -> None:
    """Test an invalid stored session key starts reauthentication."""
    authenticated_config_entry.add_to_hass(hass)
    with (
        patch(
            "pylast.User",
            return_value=MockUser(
                thrown_error=WSError(
                    "network", ERROR_CODE_INVALID_SESSION_KEY, "Invalid session key"
                )
            ),
        ),
        patch(
            "homeassistant.components.lastfm.config_flow.SessionKeyGenerator",
            return_value=MockSessionKeyGenerator(
                session_key_error=WSError(
                    "network", ERROR_CODE_TOKEN_UNAUTHORIZED, "Unauthorized token"
                )
            ),
        ),
        patch("homeassistant.components.lastfm.config_flow.POLLING_INTERVAL", 0),
        patch("homeassistant.components.lastfm.config_flow.MAX_POLLING_ATTEMPTS", 1),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert authenticated_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "auth_url"
    assert flows[0]["context"]["source"] == SOURCE_REAUTH

    hass.config_entries.flow.async_abort(flows[0]["flow_id"])
