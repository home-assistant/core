"""Test the Minecraft Server config flow."""

from asynctest import patch
from mcstatus.pinger import PingResponse

from homeassistant.components.minecraft_server.const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

STATUS_RESPONSE_RAW = {
    "description": {"text": "Dummy Description"},
    "version": {"name": "Dummy Version", "protocol": 123},
    "players": {
        "online": 3,
        "max": 10,
        "sample": [
            {"name": "Player 1", "id": "1"},
            {"name": "Player 2", "id": "2"},
            {"name": "Player 3", "id": "3"},
        ],
    },
}

USER_INPUT = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}

USER_INPUT_SAME_NAME = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "2.2.2.2",
    CONF_PORT: DEFAULT_PORT,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}

USER_INPUT_INTERVAL_SMALL = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_SCAN_INTERVAL: 4,
}

USER_INPUT_INTERVAL_LARGE = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_SCAN_INTERVAL: 86401,
}

USER_INPUT_PORT_SMALL = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "1.1.1.1",
    CONF_PORT: 1023,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}

USER_INPUT_PORT_LARGE = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "1.1.1.1",
    CONF_PORT: 65536,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}


async def test_show_config_form(hass: HomeAssistantType) -> None:
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_same_host(hass: HomeAssistantType) -> None:
    """Test abort in case of same host name."""
    unique_id = f"{USER_INPUT[CONF_HOST]}-{USER_INPUT[CONF_PORT]}"
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=unique_id, data=USER_INPUT
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_scan_interval_too_small(hass: HomeAssistantType) -> None:
    """Test error in case of a too small scan interval."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_INTERVAL_SMALL
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_scan_interval"}


async def test_scan_interval_too_large(hass: HomeAssistantType) -> None:
    """Test error in case of a too large scan interval."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_INTERVAL_LARGE
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_scan_interval"}


async def test_port_too_small(hass: HomeAssistantType) -> None:
    """Test error in case of a too small port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_PORT_SMALL
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_port"}


async def test_port_too_large(hass: HomeAssistantType) -> None:
    """Test error in case of a too large port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_PORT_LARGE
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_port"}


async def test_connection_failed(hass: HomeAssistantType) -> None:
    """Test error in case of a failed connection."""
    with patch("mcstatus.server.MinecraftServer.ping", side_effect=IOError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_connection_succeeded(hass: HomeAssistantType) -> None:
    """Test config entry in case of a successful connection."""
    with patch("mcstatus.server.MinecraftServer.ping", return_value=50):
        with patch(
            "mcstatus.server.MinecraftServer.status",
            return_value=PingResponse(STATUS_RESPONSE_RAW),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
            )

            assert result["type"] == RESULT_TYPE_CREATE_ENTRY
            assert result["title"] == f"{USER_INPUT[CONF_HOST]}:{USER_INPUT[CONF_PORT]}"
            assert result["data"][CONF_NAME] == USER_INPUT[CONF_NAME]
            assert result["data"][CONF_HOST] == USER_INPUT[CONF_HOST]
            assert result["data"][CONF_PORT] == USER_INPUT[CONF_PORT]
            assert result["data"][CONF_SCAN_INTERVAL] == USER_INPUT[CONF_SCAN_INTERVAL]
