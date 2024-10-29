"""Define tests for the Dune HD config flow."""

from unittest.mock import patch

from homeassistant.components.dunehd.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG_HOSTNAME = {CONF_HOST: "dunehd-host"}
CONFIG_IP = {CONF_HOST: "10.10.10.12"}

DUNEHD_STATE = {"protocol_version": "4", "player_state": "navigator"}


async def test_user_invalid_host(hass: HomeAssistant) -> None:
    """Test that errors are shown when the host is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "invalid/host"}
    )

    assert result["errors"] == {CONF_HOST: "invalid_host"}


async def test_user_very_long_host(hass: HomeAssistant) -> None:
    """Test that errors are shown when the host is longer than 253 chars."""
    long_host = (
        "very_long_host_very_long_host_very_long_host_very_long_host_very_long_"
        "host_very_long_host_very_long_host_very_long_host_very_long_host_very_long_"
        "host_very_long_host_very_long_host_very_long_host_very_long_host_very_long_"
        "host_very_long_host_very_long_host"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: long_host}
    )

    assert result["errors"] == {CONF_HOST: "invalid_host"}


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test that errors are shown when cannot connect to the host."""
    with patch("pdunehd.DuneHDPlayer.update_state", return_value={}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG_IP
        )

        assert result["errors"] == {CONF_HOST: "cannot_connect"}


async def test_duplicate_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when duplicates are added."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_HOSTNAME,
        title="dunehd-host",
    )
    config_entry.add_to_hass(hass)

    with patch("pdunehd.DuneHDPlayer.update_state", return_value=DUNEHD_STATE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG_HOSTNAME
        )

        assert result["errors"] == {CONF_HOST: "already_configured"}


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    with (
        patch("homeassistant.components.dunehd.async_setup_entry"),
        patch("pdunehd.DuneHDPlayer.update_state", return_value=DUNEHD_STATE),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG_HOSTNAME
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "dunehd-host"
        assert result["data"] == {CONF_HOST: "dunehd-host"}


async def test_create_entry_with_ipv6_address(hass: HomeAssistant) -> None:
    """Test that the user step works with device IPv6 address.."""
    with (
        patch("homeassistant.components.dunehd.async_setup_entry"),
        patch("pdunehd.DuneHDPlayer.update_state", return_value=DUNEHD_STATE),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: "2001:db8::1428:57ab"},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "2001:db8::1428:57ab"
        assert result["data"] == {CONF_HOST: "2001:db8::1428:57ab"}
