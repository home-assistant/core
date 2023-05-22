"""Test the RTSPtoWebRTC config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
import rtsp_to_webrtc

from homeassistant import config_entries
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.components.rtsp_to_webrtc import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ComponentSetup

from tests.common import MockConfigEntry


async def test_web_full_flow(hass: HomeAssistant) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("rtsp_to_webrtc.client.Client.heartbeat"), patch(
        "homeassistant.components.rtsp_to_webrtc.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_single_config_entry(hass: HomeAssistant) -> None:
    """Test that only a single config entry is allowed."""
    old_entry = MockConfigEntry(domain=DOMAIN, data={"example": True})
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "abort"
    assert result.get("reason") == "single_instance_allowed"


async def test_hassio_discovery(hass: HomeAssistant) -> None:
    """Test supervisor add-on discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "RTSPtoWebRTC",
                "host": "fake-server",
                "port": 8083,
            },
            name="RTSPtoWebRTC",
            slug="rtsp-to-webrtc",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result.get("type") == "form"
    assert result.get("step_id") == "hassio_confirm"
    assert result.get("description_placeholders") == {"addon": "RTSPtoWebRTC"}

    with patch("rtsp_to_webrtc.client.Client.heartbeat"), patch(
        "homeassistant.components.rtsp_to_webrtc.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

        assert result.get("type") == "create_entry"
        assert result.get("title") == "RTSPtoWebRTC"
        assert "result" in result
        assert result["result"].data == {"server_url": "http://fake-server:8083"}

        assert len(mock_setup.mock_calls) == 1


async def test_hassio_single_config_entry(hass: HomeAssistant) -> None:
    """Test supervisor add-on discovery only allows a single entry."""
    old_entry = MockConfigEntry(domain=DOMAIN, data={"example": True})
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "RTSPtoWebRTC",
                "host": "fake-server",
                "port": 8083,
            },
            name="RTSPtoWebRTC",
            slug="rtsp-to-webrtc",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result.get("type") == "abort"
    assert result.get("reason") == "single_instance_allowed"


async def test_hassio_ignored(hass: HomeAssistant) -> None:
    """Test ignoring superversor add-on discovery."""
    old_entry = MockConfigEntry(domain=DOMAIN, source=config_entries.SOURCE_IGNORE)
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "RTSPtoWebRTC",
                "host": "fake-server",
                "port": 8083,
            },
            name="RTSPtoWebRTC",
            slug="rtsp-to-webrtc",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result.get("type") == "abort"
    assert result.get("reason") == "single_instance_allowed"


async def test_hassio_discovery_server_failure(hass: HomeAssistant) -> None:
    """Test server failure during supvervisor add-on discovery shows an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "RTSPtoWebRTC",
                "host": "fake-server",
                "port": 8083,
            },
            name="RTSPtoWebRTC",
            slug="rtsp-to-webrtc",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )

    assert result.get("type") == "form"
    assert result.get("step_id") == "hassio_confirm"
    assert not result.get("errors")

    with patch(
        "rtsp_to_webrtc.client.Client.heartbeat",
        side_effect=rtsp_to_webrtc.exceptions.ResponseError(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result.get("type") == "abort"
        assert result.get("reason") == "server_failure"


async def test_options_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_integration: ComponentSetup,
) -> None:
    """Test setting stun server in options flow."""
    with patch(
        "homeassistant.components.rtsp_to_webrtc.async_setup_entry",
        return_value=True,
    ):
        await setup_integration()

    assert config_entry.state is ConfigEntryState.LOADED
    assert not config_entry.options

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    data_schema = result["data_schema"].schema
    assert set(data_schema) == {"server_url", "stun_server"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "stun_server": "example.com:1234",
        },
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert config_entry.options == {"stun_server": "example.com:1234"}

    # Clear the value
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert config_entry.options == {}


@pytest.mark.parametrize(
    ("error", "exception"),
    [
        ("server_failure", rtsp_to_webrtc.exceptions.ResponseError),
        ("server_unreachable", rtsp_to_webrtc.exceptions.ClientError),
    ],
)
async def test_options_flow_server_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    error: str,
    exception: Exception,
    rtsp_to_webrtc_client: Any,
    setup_integration: ComponentSetup,
) -> None:
    """Test setting stun server in options flow."""
    await setup_integration()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options == {"server_url": "http://127.0.0.1:8083"}

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    data_schema = result["data_schema"].schema
    assert set(data_schema) == {"server_url", "stun_server"}

    with patch(
        "rtsp_to_webrtc.client.Client.heartbeat",
        side_effect=exception(),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "server_url": "https://example.com",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] == {"server_url": error}

    with patch("rtsp_to_webrtc.client.Client.heartbeat"), patch(
        "homeassistant.components.rtsp_to_webrtc.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "server_url": "https://example.com",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_setup.call_count == 1
    assert config_entry.options == {"server_url": "https://example.com"}


async def test_options_flow_invalid_url(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    rtsp_to_webrtc_client: Any,
    setup_integration: ComponentSetup,
) -> None:
    """Test setting stun server in options flow."""
    await setup_integration()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options == {"server_url": "http://127.0.0.1:8083"}

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    data_schema = result["data_schema"].schema
    assert set(data_schema) == {"server_url", "stun_server"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "server_url": "not-a-url",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"server_url": "invalid_url"}

    with patch("rtsp_to_webrtc.client.Client.heartbeat"), patch(
        "homeassistant.components.rtsp_to_webrtc.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "server_url": "https://example.com",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_setup.call_count == 1
    assert config_entry.options == {"server_url": "https://example.com"}
