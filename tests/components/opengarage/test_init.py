"""Test OpenGarage polling and connection setup."""

from unittest.mock import MagicMock, patch

from opengarage.errors import ResponseError, TransportError
from opengarage.state import normalize_state
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TransportError("offline"), id="transport"),
        pytest.param(ResponseError(503, "http://device/jc"), id="http"),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Retry setup after library errors."""
    mock_opengarage.get_state.side_effect = error
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(None, id="null"),
        pytest.param({"_error": "invalid_json"}, id="invalid_json"),
        pytest.param({"result": 2}, id="result_only"),
    ],
)
async def test_invalid_state(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    mock_config_entry: MockConfigEntry,
    payload: dict[str, str | int] | None,
) -> None:
    """Invalid responses do not count as successful polling."""
    mock_opengarage.get_state.return_value = normalize_state(payload)
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("verify_ssl", [True, False])
async def test_session(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    mock_config_entry: MockConfigEntry,
    verify_ssl: bool,
) -> None:
    """Use the selected SSL policy without taking ownership of HA's session."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_VERIFY_SSL: verify_ssl}
    )
    with patch(
        "homeassistant.components.opengarage.opengarage.OpenGarage",
        return_value=mock_opengarage,
    ) as constructor:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert constructor.call_args.args[3] is async_get_clientsession(
        hass, verify_ssl=verify_ssl
    )
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_opengarage.close_connection.assert_not_called()
