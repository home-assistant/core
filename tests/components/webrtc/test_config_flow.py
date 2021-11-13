"""Test the WebRTC config flow."""

from homeassistant import config_entries, setup
from homeassistant.components.webrtc.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONFIG = {}


async def test_web_full_flow(hass: HomeAssistant):
    """Check full flow."""
    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["data_schema"].schema["rtsp_to_webrtc_url"] == str
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"rtsp_to_webrtc_url": "https://example.com"}
    )

    assert result["type"] == "create_entry"
    assert result["result"].data == {"rtsp_to_webrtc_url": "https://example.com"}


async def test_single_config_entry(hass):
    """Test that only a single config entry is allowed."""
    old_entry = MockConfigEntry(domain=DOMAIN, data={"example": True})
    old_entry.add_to_hass(hass)

    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"
