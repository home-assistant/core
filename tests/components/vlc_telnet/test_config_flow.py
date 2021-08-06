"""Test the VLC media player Telnet config flow."""
from unittest.mock import patch

from python_telnet_vlc.vlctelnet import AuthError, ConnectionError as ConnErr

from homeassistant import config_entries, setup
from homeassistant.components.vlc_telnet.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test successful user flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.connect"
    ), patch("homeassistant.components.vlc_telnet.config_flow.VLCTelnet.login"), patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.disconnect"
    ), patch(
        "homeassistant.components.vlc_telnet.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "VLC-TELNET"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "password": "test-password",
        "port": 4212,
        "name": "VLC-TELNET",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.connect"
    ), patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.login",
        side_effect=AuthError,
    ), patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.disconnect"
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.connect",
        side_effect=ConnErr,
    ), patch("homeassistant.components.vlc_telnet.config_flow.VLCTelnet.login"), patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.disconnect"
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
