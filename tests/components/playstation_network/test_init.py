"""Tests for PlayStation Network."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from psnawp_api.core import (
    PSNAWPAuthenticationError,
    PSNAWPClientError,
    PSNAWPForbiddenError,
    PSNAWPNotFoundError,
    PSNAWPServerError,
)
import pytest

from homeassistant.components.playstation_network.const import DOMAIN
from homeassistant.components.playstation_network.coordinator import (
    PlaystationNetworkRuntimeData,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "exception", [PSNAWPNotFoundError, PSNAWPServerError, PSNAWPClientError]
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
) -> None:
    """Test config entry not ready."""

    mock_psnawpapi.user.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_auth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test config entry auth failed setup error."""

    mock_psnawpapi.user.side_effect = PSNAWPAuthenticationError
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id


@pytest.mark.parametrize(
    "exception", [PSNAWPNotFoundError, PSNAWPServerError, PSNAWPClientError]
)
async def test_coordinator_update_data_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
) -> None:
    """Test coordinator data update failed."""

    mock_psnawpapi.user.return_value.get_presence.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_update_auth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test coordinator update auth failed setup error."""

    mock_psnawpapi.user.return_value.get_presence.side_effect = (
        PSNAWPAuthenticationError
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id


async def test_trophy_title_coordinator(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trophy title coordinator updates when PS Vita is registered."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert len(mock_psnawpapi.user.return_value.trophy_titles.mock_calls) == 1

    freezer.tick(timedelta(days=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(mock_psnawpapi.user.return_value.trophy_titles.mock_calls) == 2


async def test_trophy_title_coordinator_auth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trophy title coordinator starts reauth on authentication error."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_psnawpapi.user.return_value.trophy_titles.side_effect = (
        PSNAWPAuthenticationError
    )

    freezer.tick(timedelta(days=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id


@pytest.mark.parametrize(
    "exception", [PSNAWPNotFoundError, PSNAWPServerError, PSNAWPClientError]
)
async def test_trophy_title_coordinator_update_data_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trophy title coordinator update failed."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_psnawpapi.user.return_value.trophy_titles.side_effect = exception

    freezer.tick(timedelta(days=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    runtime_data: PlaystationNetworkRuntimeData = config_entry.runtime_data
    assert runtime_data.trophy_titles.last_update_success is False


async def test_trophy_title_coordinator_doesnt_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trophy title coordinator does not update if no PS Vita is registered."""

    mock_psnawpapi.me.return_value.get_account_devices.return_value = [
        {"deviceType": "PS5"},
        {"deviceType": "PS3"},
    ]
    mock_psnawpapi.me.return_value.get_profile_legacy.return_value = {
        "profile": {"presences": []}
    }
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert len(mock_psnawpapi.user.return_value.trophy_titles.mock_calls) == 1

    freezer.tick(timedelta(days=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(mock_psnawpapi.user.return_value.trophy_titles.mock_calls) == 1


async def test_trophy_title_coordinator_play_new_game(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test we play a new game and get a title image on next trophy titles update."""

    _tmp = mock_psnawpapi.user.return_value.trophy_titles.return_value
    mock_psnawpapi.user.return_value.trophy_titles.return_value = []

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("media_player.playstation_vita"))
    assert state.attributes.get("entity_picture") is None

    mock_psnawpapi.user.return_value.trophy_titles.return_value = _tmp

    freezer.tick(timedelta(days=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_psnawpapi.user.return_value.trophy_titles.mock_calls) == 2

    assert (state := hass.states.get("media_player.playstation_vita"))
    assert (
        state.attributes["entity_picture"]
        == "https://image.api.playstation.com/trophy/np/NPWR03134_00_0008206095F67FD3BB385E9E00A7C9CFE6F5A4AB96/5F87A6997DD23D1C4D4CC0D1F958ED79CB905331.PNG"
    )


@pytest.mark.parametrize(
    "exception",
    [PSNAWPNotFoundError, PSNAWPServerError, PSNAWPClientError, PSNAWPForbiddenError],
)
async def test_friends_coordinator_update_data_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
) -> None:
    """Test friends coordinator setup fails in _update_data."""

    mock = mock_psnawpapi.user.return_value.friends_list.return_value[0]
    mock.get_presence.side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (PSNAWPNotFoundError, ConfigEntryState.SETUP_ERROR),
        (PSNAWPAuthenticationError, ConfigEntryState.SETUP_ERROR),
        (PSNAWPServerError, ConfigEntryState.SETUP_RETRY),
        (PSNAWPClientError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_friends_coordinator_setup_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test friends coordinator setup fails in _async_setup."""
    mock = mock_psnawpapi.user.return_value.friends_list.return_value[0]
    mock.profile.side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state


async def test_friends_coordinator_auth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test friends coordinator starts reauth on authentication error."""

    mock = mock_psnawpapi.user.return_value.friends_list.return_value[0]
    mock.profile.side_effect = PSNAWPAuthenticationError

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id
