"""Device actions for INELNET Blinds."""

from __future__ import annotations

from typing import Any

from inelnet_api import InelnetChannel
import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import ACTION_DOWN_SHORT, ACTION_PROGRAM, ACTION_UP_SHORT, DOMAIN, Action

ACTION_TYPES = {
    ACTION_UP_SHORT,
    ACTION_DOWN_SHORT,
    ACTION_PROGRAM,
}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required("type"): vol.In(ACTION_TYPES),
    }
)


def _action_code(action_type: str) -> Action:
    """Map action type string to Action enum."""
    return {
        ACTION_UP_SHORT: Action.UP_SHORT,
        ACTION_DOWN_SHORT: Action.DOWN_SHORT,
        ACTION_PROGRAM: Action.PROGRAM,
    }[action_type]


def _device_to_client_and_channel(
    hass: HomeAssistant, device_id: str
) -> tuple[Any, int] | tuple[None, None]:
    """Resolve device_id to (client, channel). Returns (None, None) if not our device."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(device_id)
    if not device or not device.config_entries:
        return None, None
    for identifier in device.identifiers:
        if identifier[0] != DOMAIN or "-ch" not in str(identifier[1]):
            continue
        try:
            _, ch_str = str(identifier[1]).rsplit("-ch", 1)
            channel = int(ch_str)
        except ValueError, TypeError:
            continue
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if not entry or entry.domain != DOMAIN:
                continue
            if not getattr(entry, "runtime_data", None):
                continue
            data = entry.runtime_data
            clients = getattr(data, "clients", None)
            if clients and channel in clients:
                return clients[channel], channel
            host = getattr(data, "host", None)
            if host:
                return InelnetChannel(host, channel), channel
    return None, None


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device actions for INELNET devices."""
    client, _ = _device_to_client_and_channel(hass, device_id)
    if client is None:
        return []

    return [
        {"domain": DOMAIN, "device_id": device_id, "type": ACTION_UP_SHORT},
        {"domain": DOMAIN, "device_id": device_id, "type": ACTION_DOWN_SHORT},
        {"domain": DOMAIN, "device_id": device_id, "type": ACTION_PROGRAM},
    ]


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate action config (device_id-based; no entity_id)."""
    return ACTION_SCHEMA(config)


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute device action."""
    client, _ = _device_to_client_and_channel(hass, config[CONF_DEVICE_ID])
    if client is None:
        return
    action_type = config.get("type")
    if action_type not in ACTION_TYPES:
        return
    code = _action_code(action_type)
    session = async_get_clientsession(hass)
    await client.send_command(code, session=session)
