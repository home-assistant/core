"""Class to manage devices."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
import logging
from typing import Any

from voip_utils import CallInfo, VoipDatagramProtocol
from voip_utils.sip import SipEndpoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VER

_LOGGER = logging.getLogger(__name__)


@dataclass
class VoIPDevice:
    """Class to store device."""

    voip_id: str
    device_id: str
    is_active: bool = False
    update_listeners: list[Callable[[VoIPDevice], None]] = field(default_factory=list)
    protocol: VoipDatagramProtocol | None = None
    contact: SipEndpoint | None = None

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

    def get_pipeline_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for pipeline select."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id("select", DOMAIN, f"{self.voip_id}-pipeline")

    def get_vad_sensitivity_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for VAD sensitivity."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "select", DOMAIN, f"{self.voip_id}-vad_sensitivity"
        )


class VoIPDevices:
    """Class to store devices."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize VoIP devices."""
        self.hass = hass
        self.config_entry = config_entry
        self._new_device_listeners: list[Callable[[VoIPDevice], None]] = []
        self.devices: dict[str, VoIPDevice] = {}
        self.device_stores: dict[str, Store] = {}

    async def async_setup(self) -> None:
        """Set up devices."""
        for device in dr.async_entries_for_config_entry(
            dr.async_get(self.hass), self.config_entry.entry_id
        ):
            voip_id = next(
                (item[1] for item in device.identifiers if item[0] == DOMAIN), None
            )
            if voip_id is None:
                continue
            device_store = self.device_stores[voip_id] = Store(
                self.hass, STORAGE_VER, f"voip-device-{voip_id}"
            )
            device_data: dict[str, Any] = await device_store.async_load() or {}
            self.devices[voip_id] = VoIPDevice(
                voip_id=voip_id,
                device_id=device.id,
                contact=SipEndpoint(device_data.get("contact"))
                if device_data.get("contact")
                else None,
            )

        @callback
        def async_device_removed(ev: Event[dr.EventDeviceRegistryUpdatedData]) -> None:
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
                callback(lambda event_data: event_data["action"] == "remove"),
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
        if call_info.caller_endpoint is None:
            raise RuntimeError("Could not identify VOIP caller")
        voip_id = call_info.caller_endpoint.uri
        voip_device = self.devices.get(voip_id)

        if voip_device is None:
            # If we couldn't find the device based on SIP URI, see if we can
            # find an old device based on just the host/IP and migrate it
            old_id = call_info.caller_endpoint.host
            voip_device = self.devices.get(old_id)
            if voip_device is not None:
                voip_device.voip_id = voip_id
                self.devices[voip_id] = voip_device
                dev_reg.async_update_device(
                    voip_device.device_id, new_identifiers={(DOMAIN, voip_id)}
                )
                # Migrate entities
                old_prefix = f"{old_id}-"

                def entity_migrator(entry: er.RegistryEntry) -> dict[str, Any] | None:
                    """Migrate entities."""
                    if not entry.unique_id.startswith(old_prefix):
                        return None
                    key = entry.unique_id[len(old_prefix) :]
                    return {
                        "new_unique_id": f"{voip_id}-{key}",
                    }

                self.config_entry.async_create_task(
                    self.hass,
                    er.async_migrate_entries(
                        self.hass, self.config_entry.entry_id, entity_migrator
                    ),
                    f"voip migrating entities {voip_id}",
                )

        # Update device with latest info
        device = dev_reg.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, voip_id)},
            name=call_info.caller_endpoint.host,
            manufacturer=manuf,
            model=model,
            sw_version=fw_version,
            configuration_url=f"http://{call_info.caller_ip}",
        )

        if voip_device is not None:
            if voip_device.contact is None and call_info.contact_endpoint is not None:
                # Update VOIP device with contact information from call info
                voip_device.contact = call_info.contact_endpoint
                self.hass.async_create_task(
                    self.async_update_device_store(
                        voip_id, call_info.contact_endpoint.sip_header
                    )
                )
            return voip_device

        voip_device = self.devices[voip_id] = VoIPDevice(
            voip_id=voip_id, device_id=device.id, contact=call_info.contact_endpoint
        )
        if call_info.contact_endpoint is not None:
            self.hass.async_create_task(
                self.async_update_device_store(
                    voip_id, call_info.contact_endpoint.sip_header
                )
            )

        for listener in self._new_device_listeners:
            listener(voip_device)

        return voip_device

    async def async_update_device_store(self, voip_id: str, contact_header: str):
        """Update the device store with the contact information."""
        _LOGGER.debug("Saving new VOIP device %s contact %s", voip_id, contact_header)
        if voip_id not in self.device_stores:
            _LOGGER.debug("Creating store for %s", voip_id)
            self.device_stores[voip_id] = Store(
                self.hass, STORAGE_VER, f"voip-device-{voip_id}"
            )
        device_store = self.device_stores[voip_id]
        device_data: dict[str, Any] = await device_store.async_load() or {}
        device_data["contact"] = contact_header
        await device_store.async_save(device_data)
        _LOGGER.debug("Saved new VOIP device contact")

    def __iter__(self) -> Iterator[VoIPDevice]:
        """Iterate over devices."""
        return iter(self.devices.values())
