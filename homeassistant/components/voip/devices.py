"""Class to manage devices."""
from __future__ import annotations

from collections.abc import Callable

from voip_utils import CallInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN


class VoIPDevices:
    """Class to store devices."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize VoIP devices."""
        self.hass = hass
        self.config_entry = config_entry
        self._new_device_listeners: list[Callable[[dr.DeviceEntry], None]] = []

    @callback
    def async_add_new_device_listener(
        self, listener: Callable[[dr.DeviceEntry], None]
    ) -> None:
        """Add a new device listener."""
        self._new_device_listeners.append(listener)

    @callback
    def async_allow_call(self, call_info: CallInfo) -> bool:
        """Check if a call is allowed."""
        dev_reg = dr.async_get(self.hass)
        ip_address = call_info.caller_ip

        user_agent = call_info.headers.get("user-agent", "")
        user_agent_parts = user_agent.split()
        if len(user_agent_parts) == 3 and user_agent_parts[0] == "Grandstream":
            manuf = user_agent_parts[0]
            model = user_agent_parts[1]
            fw_version = user_agent_parts[2]
        else:
            manuf = None
            model = user_agent if user_agent else None
            fw_version = None

        device = dev_reg.async_get_device({(DOMAIN, ip_address)})

        if device is None:
            device = dev_reg.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                identifiers={(DOMAIN, ip_address)},
                name=ip_address,
                manufacturer=manuf,
                model=model,
                sw_version=fw_version,
            )
            for listener in self._new_device_listeners:
                listener(device)
            return False

        if fw_version is not None and device.sw_version != fw_version:
            dev_reg.async_update_device(device.id, sw_version=fw_version)

        ent_reg = er.async_get(self.hass)

        allowed_call_entity_id = ent_reg.async_get_entity_id(
            "switch", DOMAIN, f"{ip_address}-allow_call"
        )
        # If 2 requests come in fast, the device registry entry has been created
        # but entity might not exist yet.
        if allowed_call_entity_id is None:
            return False

        if state := self.hass.states.get(allowed_call_entity_id):
            return state.state == "on"

        return False
