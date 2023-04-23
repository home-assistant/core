"""Class to manage devices."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from voip_utils import CallInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN


@dataclass
class VoIPDevice:
    """Class to store device."""

    voip_id: str
    device_id: str
    is_active: bool = False
    update_listeners: list[Callable[[VoIPDevice], None]] = field(default_factory=list)

    @callback
    def set_is_active(self, active: bool) -> None:
        """Set active state."""
        self.is_active = active
        for listener in self.update_listeners:
            listener(self)

    @callback
    def async_listen_update(
        self, listener: Callable[[VoIPDevice], None]
    ) -> Callable[[], None]:
        """Listen for updates."""
        self.update_listeners.append(listener)
        return lambda: self.update_listeners.remove(listener)

    @callback
    def async_allow_call(self, hass: HomeAssistant) -> bool:
        """Return if call is allowed."""
        ent_reg = er.async_get(hass)

        allowed_call_entity_id = ent_reg.async_get_entity_id(
            "switch", DOMAIN, f"{self.voip_id}-allow_call"
        )
        # If 2 requests come in fast, the device registry entry has been created
        # but entity might not exist yet.
        if allowed_call_entity_id is None:
            return False

        if state := hass.states.get(allowed_call_entity_id):
            return state.state == "on"

        return False


class VoIPDevices:
    """Class to store devices."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize VoIP devices."""
        self.hass = hass
        self.config_entry = config_entry
        self._new_device_listeners: list[Callable[[VoIPDevice], None]] = []
        self.devices: dict[str, VoIPDevice] = {}

    @callback
    def async_setup(self) -> None:
        """Set up devices."""
        for device in dr.async_entries_for_config_entry(
            dr.async_get(self.hass), self.config_entry.entry_id
        ):
            voip_id = next(
                (item[1] for item in device.identifiers if item[0] == DOMAIN), None
            )
            if voip_id is None:
                continue
            self.devices[voip_id] = VoIPDevice(
                voip_id=voip_id,
                device_id=device.id,
            )

        @callback
        def async_device_removed(ev: Event) -> None:
            """Handle device removed."""
            removed_id = ev.data["device_id"]
            self.devices = {
                voip_id: voip_device
                for voip_id, voip_device in self.devices.items()
                if voip_device.device_id != removed_id
            }

        self.config_entry.async_on_unload(
            self.hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                async_device_removed,
                callback(lambda ev: ev.data.get("action") == "remove"),
            )
        )

    @callback
    def async_add_new_device_listener(
        self, listener: Callable[[VoIPDevice], None]
    ) -> None:
        """Add a new device listener."""
        self._new_device_listeners.append(listener)

    @callback
    def async_get_or_create(self, call_info: CallInfo) -> VoIPDevice:
        """Get or create a device."""
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

        dev_reg = dr.async_get(self.hass)
        voip_id = call_info.caller_ip
        voip_device = self.devices.get(voip_id)

        if voip_device is not None:
            device = dev_reg.async_get(voip_device.device_id)
            if device and fw_version and device.sw_version != fw_version:
                dev_reg.async_update_device(device.id, sw_version=fw_version)

            return voip_device

        device = dev_reg.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, voip_id)},
            name=voip_id,
            manufacturer=manuf,
            model=model,
            sw_version=fw_version,
        )
        voip_device = self.devices[voip_id] = VoIPDevice(
            voip_id=voip_id,
            device_id=device.id,
        )
        for listener in self._new_device_listeners:
            listener(voip_device)

        return voip_device

    def __iter__(self) -> Iterator[VoIPDevice]:
        """Iterate over devices."""
        return iter(self.devices.values())
