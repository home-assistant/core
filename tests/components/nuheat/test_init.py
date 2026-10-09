"""NuHeat component tests."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from homeassistant.components.nuheat.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .mocks import MOCK_CONFIG_ENTRY, _get_mock_nuheat

from tests.common import MockConfigEntry

VALID_CONFIG = {
    "nuheat": {"username": "warm", "password": "feet", "devices": "thermostat123"}
}
INVALID_CONFIG = {"nuheat": {"username": "warm", "password": "feet"}}


async def test_init_success(hass: HomeAssistant) -> None:
    """Test that we can setup with valid config."""
    mock_nuheat = _get_mock_nuheat()

    with patch(
        "homeassistant.components.nuheat.nuheat.NuHeat",
        return_value=mock_nuheat,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(
            requests.exceptions.HTTPError(response=MagicMock(status_code=401)),
            id="unauthorized",
        ),
        pytest.param(Exception("Boom"), id="unknown"),
    ],
)
async def test_init_login_failed(hass: HomeAssistant, exception: Exception) -> None:
    """Test setup fails when logging in fails."""
    mock_nuheat = _get_mock_nuheat()
    mock_nuheat.authenticate.side_effect = exception

    with patch(
        "homeassistant.components.nuheat.nuheat.NuHeat",
        return_value=mock_nuheat,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.reason == "Failed to log in to NuHeat"
