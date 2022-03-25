"""Tests for the samsungtv component."""
from __future__ import annotations

from unittest.mock import Mock

from async_upnp_client.client import UpnpAction, UpnpService

from homeassistant.components.samsungtv.const import DOMAIN
from homeassistant.components.samsungtv.media_player import UpnpServiceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_samsungtv_entry(hass: HomeAssistant, data: ConfigType) -> ConfigEntry:
    """Set up mock Samsung TV from config entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=data, entry_id="123456", unique_id="any"
    )
    entry.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    return entry


def upnp_get_action_mock(
    device: Mock, service_type: UpnpServiceType, action: str
) -> Mock:
    """Get or Add UpnpService/UpnpAction to UpnpDevice mock."""
    upnp_service: Mock | None
    if (upnp_service := device.services.get(service_type)) is None:
        upnp_service = Mock(UpnpService)
        upnp_service.actions = {}

        def _get_action(action: str):
            return upnp_service.actions.get(action)

        upnp_service.action.side_effect = _get_action
        device.services[service_type.value] = upnp_service

    upnp_action: Mock | None
    if (upnp_action := upnp_service.actions.get(action)) is None:
        upnp_action = Mock(UpnpAction)
        upnp_service.actions[action] = upnp_action

    return upnp_action
