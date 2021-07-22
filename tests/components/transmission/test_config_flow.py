"""Tests for Transmission config flow."""
from datetime import timedelta
from unittest.mock import MagicMock

from transmissionrpc.error import TransmissionError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.transmission.const import CONF_LIMIT, CONF_ORDER, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from . import MOCK_CONFIG

from tests.common import MockConfigEntry

NAME = "Transmission"
HOST = "192.168.1.100"
USERNAME = "username"
PASSWORD = "password"
PORT = 9091
SCAN_INTERVAL = 10

MOCK_ENTRY = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_PORT: PORT,
}


async def test_flow_works(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Transmission"
    assert result["data"] == MOCK_CONFIG


async def test_options(hass: HomeAssistant) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CONF_NAME,
        data=MOCK_ENTRY,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: 30,
            CONF_LIMIT: 5,
            CONF_ORDER: "oldest_first",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_SCAN_INTERVAL: 30,
        CONF_LIMIT: 5,
        CONF_ORDER: "oldest_first",
    }


async def test_import_success(hass: HomeAssistant) -> None:
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_NAME: "Transmission",
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_PORT: "9091",
            CONF_SCAN_INTERVAL: timedelta(seconds=20),
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Transmission"
    assert result["data"] == {
        CONF_NAME: "Transmission",
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_PORT: "9091",
        CONF_SCAN_INTERVAL: 20,
    }


async def test_host_port_already_configured(hass: HomeAssistant) -> None:
    """Test host is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY, unique_id="1.2.3.4:9091")
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_error_on_wrong_credentials(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test with wrong credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api.side_effect = TransmissionError("401: Unauthorized")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {
        CONF_USERNAME: "invalid_auth",
        CONF_PASSWORD: "invalid_auth",
    }


async def test_error_on_connection_failure(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test when connection to host fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api.side_effect = TransmissionError("111: Connection refused")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_error_on_unknown_error(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test when connection to host fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api.side_effect = TransmissionError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="1.2.3.4:9091",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": "1.2.3.4:9091",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-user", CONF_PASSWORD: "test-password"},
    )

    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"


async def test_reauth_failed(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="1.2.3.4:9091",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": "1.2.3.4:9091",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    mock_api.side_effect = TransmissionError("401: Unauthorized")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-user", CONF_PASSWORD: "test-password"},
    )
    assert result2["type"] == "form"
    assert result2["errors"] == {
        CONF_USERNAME: "invalid_auth",
        CONF_PASSWORD: "invalid_auth",
    }
