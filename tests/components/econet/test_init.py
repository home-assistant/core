"""Tests for the EcoNet integration setup."""

from unittest.mock import patch

from aiohttp import ClientError
from pyeconet.errors import PyeconetError
import pytest

from homeassistant.components.econet.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(PyeconetError(), id="library_error"),
        pytest.param(ClientError("certificate has expired"), id="client_error"),
    ],
)
async def test_login_error_retries_setup(
    hass: HomeAssistant, exception: Exception
) -> None:
    """Test setup is retried when logging in fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "admin@localhost.com", CONF_PASSWORD: "password0"},
    )
    entry.add_to_hass(hass)

    with patch("pyeconet.EcoNetApiInterface.login", side_effect=exception):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
