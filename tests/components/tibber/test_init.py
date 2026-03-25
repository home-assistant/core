"""Test loading of the Tibber config entry."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber import DOMAIN, TibberRuntimeData, async_setup_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from tests.common import MockConfigEntry


async def test_entry_unload(
    recorder_mock: Recorder, hass: HomeAssistant, mock_tibber_setup: MagicMock
) -> None:
    """Test unloading the entry."""
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, "tibber")
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    mock_tibber_setup.rt_disconnect.assert_called_once()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("recorder_mock")
async def test_data_api_runtime_creates_client(hass: HomeAssistant) -> None:
    """Ensure the data API runtime creates and caches the client."""
    session = MagicMock()
    session.async_ensure_token_valid = AsyncMock()
    session.token = {CONF_ACCESS_TOKEN: "access-token"}

    runtime = TibberRuntimeData(
        session=session,
    )

    with patch("homeassistant.components.tibber.tibber.Tibber") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.set_access_token = MagicMock()
        mock_client_cls.return_value = mock_client

        client = await runtime.async_get_client(hass)

        mock_client_cls.assert_called_once_with(
            access_token="access-token", websession=ANY, time_zone=ANY, ssl=ANY
        )
        session.async_ensure_token_valid.assert_awaited_once()
        mock_client.set_access_token.assert_called_once_with("access-token")
        assert client is mock_client

        mock_client.set_access_token.reset_mock()
        session.async_ensure_token_valid.reset_mock()

        cached_client = await runtime.async_get_client(hass)

        mock_client_cls.assert_called_once()
        session.async_ensure_token_valid.assert_awaited_once()
        mock_client.set_access_token.assert_called_once_with("access-token")
        assert cached_client is client


@pytest.mark.usefixtures("recorder_mock")
async def test_data_api_runtime_missing_token_raises(hass: HomeAssistant) -> None:
    """Ensure missing tokens trigger reauthentication."""
    session = MagicMock()
    session.async_ensure_token_valid = AsyncMock()
    session.token = {}

    runtime = TibberRuntimeData(
        session=session,
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await runtime.async_get_client(hass)
    session.async_ensure_token_valid.assert_awaited_once()


async def test_setup_requires_data_api_reauth(hass: HomeAssistant) -> None:
    """Ensure legacy entries trigger reauth to configure Data API."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: "legacy-token"},
        unique_id="legacy",
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await async_setup_entry(hass, entry)
