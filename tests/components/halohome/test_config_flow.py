"""HALO Home integration config flow tests."""
from unittest.mock import patch

import halohome

from homeassistant import config_entries
from homeassistant.components.halohome.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_CREATE_ENTRY

from tests.common import MockConfigEntry

HOST = "http://127.0.0.1"
MODULE = "homeassistant.components.halohome"
USERNAME = "example@example.com"
USER_ID = 12345678
TITLE = f"HALO Home ({USER_ID})"
PASSWORD = "TestPassword"
CONFIG_ENTRY = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_HOST: HOST,
}


class MockConnection:
    """A mocked Connection object for the halohome library."""

    user_id = USER_ID


def _patch_connect(raise_error: bool = False):
    async def _connect(email: str, password: str, host: str):
        if raise_error:
            raise halohome.HaloHomeError("Test login error")
        return MockConnection()

    return patch("halohome.connect", new=_connect)


async def test_manual_setup(hass: HomeAssistant):
    """Test successful configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_connect(), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG_ENTRY,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == CONFIG_ENTRY
    assert result["title"] == TITLE
    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_setup_already_exists(hass: HomeAssistant):
    """Test configuration flow when already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_ENTRY,
        unique_id=str(USER_ID),
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_connect():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_ENTRY
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_manual_setup_connection_exception(hass: HomeAssistant):
    """Test configuration flow with a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_connect(raise_error=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_ENTRY
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
