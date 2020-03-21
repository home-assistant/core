"""Test the Minecraft Server config flow."""

from asynctest import patch
from mcstatus.pinger import PingResponse

from homeassistant.components.minecraft_server.const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
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
    CONF_HOST: "mc.dummyserver.com",
    CONF_PORT: DEFAULT_PORT,
}

USER_INPUT_IPV4 = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
}

USER_INPUT_IPV6 = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "::ffff:0101:0101",
    CONF_PORT: DEFAULT_PORT,
}

USER_INPUT_PORT_TOO_SMALL = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "mc.dummyserver.com",
    CONF_PORT: 1023,
}

USER_INPUT_PORT_TOO_LARGE = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "mc.dummyserver.com",
    CONF_PORT: 65536,
}


async def test_show_config_form(hass: HomeAssistantType) -> None:
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_invalid_ip(hass: HomeAssistantType) -> None:
    """Test error in case of an invalid IP address."""
    with patch("getmac.get_mac_address", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_IPV4
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_ip"}


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


async def test_port_too_small(hass: HomeAssistantType) -> None:
    """Test error in case of a too small port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_PORT_TOO_SMALL
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_port"}


async def test_port_too_large(hass: HomeAssistantType) -> None:
    """Test error in case of a too large port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_PORT_TOO_LARGE
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_port"}


async def test_connection_failed(hass: HomeAssistantType) -> None:
    """Test error in case of a failed connection."""
    with patch("mcstatus.server.MinecraftServer.ping", side_effect=OSError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_connection_succeeded_with_host(hass: HomeAssistantType) -> None:
    """Test config entry in case of a successful connection with a host name."""
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


async def test_connection_succeeded_with_ip4(hass: HomeAssistantType) -> None:
    """Test config entry in case of a successful connection with an IPv4 address."""
    with patch("getmac.get_mac_address", return_value="01:23:45:67:89:ab"):
        with patch("mcstatus.server.MinecraftServer.ping", return_value=50):
            with patch(
                "mcstatus.server.MinecraftServer.status",
                return_value=PingResponse(STATUS_RESPONSE_RAW),
            ):
                result = await hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_IPV4
                )

                assert result["type"] == RESULT_TYPE_CREATE_ENTRY
                assert (
                    result["title"]
                    == f"{USER_INPUT_IPV4[CONF_HOST]}:{USER_INPUT_IPV4[CONF_PORT]}"
                )
                assert result["data"][CONF_NAME] == USER_INPUT_IPV4[CONF_NAME]
                assert result["data"][CONF_HOST] == USER_INPUT_IPV4[CONF_HOST]
                assert result["data"][CONF_PORT] == USER_INPUT_IPV4[CONF_PORT]


async def test_connection_succeeded_with_ip6(hass: HomeAssistantType) -> None:
    """Test config entry in case of a successful connection with an IPv6 address."""
    with patch("getmac.get_mac_address", return_value="01:23:45:67:89:ab"):
        with patch("mcstatus.server.MinecraftServer.ping", return_value=50):
            with patch(
                "mcstatus.server.MinecraftServer.status",
                return_value=PingResponse(STATUS_RESPONSE_RAW),
            ):
                result = await hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_IPV6
                )

                assert result["type"] == RESULT_TYPE_CREATE_ENTRY
                assert (
                    result["title"]
                    == f"{USER_INPUT_IPV6[CONF_HOST]}:{USER_INPUT_IPV6[CONF_PORT]}"
                )
                assert result["data"][CONF_NAME] == USER_INPUT_IPV6[CONF_NAME]
                assert result["data"][CONF_HOST] == USER_INPUT_IPV6[CONF_HOST]
                assert result["data"][CONF_PORT] == USER_INPUT_IPV6[CONF_PORT]
