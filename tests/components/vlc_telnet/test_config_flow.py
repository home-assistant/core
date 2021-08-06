"""Test the VLC media player Telnet config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest
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
                "password": "test-password",
                "host": "1.1.1.1",
                "port": 8888,
                "name": "custom name",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "custom name"
    assert result2["data"] == {
        "password": "test-password",
        "host": "1.1.1.1",
        "port": 8888,
        "name": "custom name",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test successful import flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.connect"
    ), patch("homeassistant.components.vlc_telnet.config_flow.VLCTelnet.login"), patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.disconnect"
    ), patch(
        "homeassistant.components.vlc_telnet.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "password": "test-password",
                "host": "1.1.1.1",
                "port": 8888,
                "name": "custom name",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "custom name"
    assert result["data"] == {
        "password": "test-password",
        "host": "1.1.1.1",
        "port": 8888,
        "name": "custom name",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_USER, config_entries.SOURCE_IMPORT]
)
@pytest.mark.parametrize(
    "error, connect_side_effect, login_side_effect",
    [
        ("invalid_auth", None, AuthError),
        ("cannot_connect", ConnErr, None),
        ("unknown", Exception, None),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    error: str,
    connect_side_effect: Exception | None,
    login_side_effect: Exception | None,
    source: str,
) -> None:
    """Test we handle form errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}
    )

    with patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.connect",
        side_effect=connect_side_effect,
    ), patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.login",
        side_effect=login_side_effect,
    ), patch(
        "homeassistant.components.vlc_telnet.config_flow.VLCTelnet.disconnect"
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "test-password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": error}
