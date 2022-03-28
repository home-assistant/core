"""Tests for the samsungtv component."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

from async_upnp_client.client import UpnpAction, UpnpService

from homeassistant.components import ssdp
from homeassistant.components.samsungtv.const import (
    CONF_MODEL,
    DOMAIN,
    ENTRY_RELOAD_COOLDOWN,
    METHOD_WEBSOCKET,
)
from homeassistant.components.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_METHOD, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_WS_ENTRY = {
    CONF_HOST: "fake_host",
    CONF_METHOD: METHOD_WEBSOCKET,
    CONF_PORT: 8002,
    CONF_MODEL: "any",
    CONF_NAME: "any",
}

MOCK_SSDP_DATA_RENDERING_CONTROL_ST = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="urn:schemas-upnp-org:service:RenderingControl:1",
    ssdp_location="https://fake_host:12345/test",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: "[TV] fake_name",
        ATTR_UPNP_MANUFACTURER: "Samsung fake_manufacturer",
        ATTR_UPNP_MODEL_NAME: "fake_model",
        ATTR_UPNP_UDN: "uuid:0d1cef00-00dc-1000-9c80-4844f7b172de",
    },
)
MOCK_SSDP_DATA_MAIN_TV_AGENT_ST = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="urn:samsung.com:service:MainTVAgent2:1",
    ssdp_location="https://fake_host:12345/test",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: "[TV] fake_name",
        ATTR_UPNP_MANUFACTURER: "Samsung fake_manufacturer",
        ATTR_UPNP_MODEL_NAME: "fake_model",
        ATTR_UPNP_UDN: "uuid:0d1cef00-00dc-1000-9c80-4844f7b172de",
    },
)


async def async_wait_config_entry_reload(hass: HomeAssistant) -> None:
    """Wait for the config entry to reload."""
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()


async def setup_samsungtv_entry(hass: HomeAssistant, data: ConfigType) -> ConfigEntry:
    """Set up mock Samsung TV from config entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=data, entry_id="123456", unique_id="any"
    )
    entry.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    return entry


def upnp_get_action_mock(device: Mock, service_type: str, action: str) -> Mock:
    """Get or Add UpnpService/UpnpAction to UpnpDevice mock."""
    upnp_service: Mock | None
    if (upnp_service := device.services.get(service_type)) is None:
        upnp_service = Mock(UpnpService)
        upnp_service.actions = {}

        def _get_action(action: str):
            return upnp_service.actions.get(action)

        upnp_service.action.side_effect = _get_action
        device.services[service_type] = upnp_service

    upnp_action: Mock | None
    if (upnp_action := upnp_service.actions.get(action)) is None:
        upnp_action = Mock(UpnpAction)
        upnp_service.actions[action] = upnp_action

    return upnp_action
