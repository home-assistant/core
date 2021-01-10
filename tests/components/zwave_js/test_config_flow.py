"""Test the Z-Wave JS config flow."""
import asyncio
from unittest.mock import patch

from zwave_js_server.version import VersionInfo

from homeassistant import config_entries, setup
from homeassistant.components.zwave_js.const import DOMAIN


async def test_user_step_full(hass):
    """Test we create an entry with user step."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    with patch(
        "homeassistant.components.zwave_js.config_flow.get_server_version",
        return_value=VersionInfo(
            driver_version="mock-driver-version",
            server_version="mock-server-version",
            home_id=1234,
        ),
    ), patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "ws://localhost:3000",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Z-Wave JS"
    assert result2["data"] == {
        "url": "ws://localhost:3000",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert result2["result"].unique_id == 1234


async def test_user_step_invalid_input(hass):
    """Test we handle invalid auth in the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.zwave_js.config_flow.get_server_version",
        side_effect=asyncio.TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "ws://localhost:3000",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "not-ws-url",
        },
    )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "invalid_ws_url"}


async def test_user_step_unexpected_exception(hass):
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.zwave_js.config_flow.get_server_version",
        side_effect=Exception("Boom"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "ws://localhost:3000",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
