"""Event entities for the Bang & Olufsen integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mozart_api.models import PairedRemote

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BeoConfigEntry
from .const import (
    BEO_REMOTE_KEY_EVENTS,
    CONNECTION_STATUS,
    DEVICE_BUTTON_EVENTS,
    DOMAIN,
    MANUFACTURER,
    BeoModel,
    WebsocketNotification,
)
from .entity import BeoEntity
from .util import get_device_buttons, get_remote_keys, get_remotes

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BeoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Event entities from config entry."""
    entities: list[BeoEvent] = [
        BeoButtonEvent(config_entry, button_type)
        for button_type in get_device_buttons(config_entry.data[CONF_MODEL])
    ]

    # Check for connected Beoremote One
    remotes = await get_remotes(config_entry.runtime_data.client)

    for remote in remotes:
        entities.extend(
            [
                BeoRemoteKeyEvent(config_entry, remote, key_type)
                for key_type in get_remote_keys()
            ]
        )

    # If the remote is no longer available, then delete the device.
    # The remote may appear as being available to the device after it has been unpaired on the remote
    # As it has to be removed from the device on the app.

    device_registry = dr.async_get(hass)
    devices = device_registry.devices.get_devices_for_config_entry_id(
        config_entry.entry_id
    )
    for device in devices:
        if device.model == BeoModel.BEOREMOTE_ONE and device.serial_number not in {
            remote.serial_number for remote in remotes
        }:
            device_registry.async_update_device(
                device.id, remove_config_entry_id=config_entry.entry_id
            )

    async_add_entities(new_entities=entities)


class BeoEvent(BeoEntity, EventEntity):
    """Base Event class."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_entity_registry_enabled_default = False

    def __init__(self, config_entry: BeoConfigEntry) -> None:
        """Initialize Event."""
        super().__init__(config_entry, config_entry.runtime_data.client)

    @callback
    def _async_handle_event(self, event: str) -> None:
        """Handle event."""
        self._trigger_event(event)
        self.async_write_ha_state()


class BeoButtonEvent(BeoEvent):
    """Event class for Button events."""

    _attr_event_types = DEVICE_BUTTON_EVENTS

    def __init__(self, config_entry: BeoConfigEntry, button_type: str) -> None:
        """Initialize Button."""
        super().__init__(config_entry)

        self._attr_unique_id = f"{self._unique_id}_{button_type}"

        # Make the native button name Home Assistant compatible
        self._attr_translation_key = button_type.lower()

        self._button_type = button_type

    async def async_added_to_hass(self) -> None:
        """Listen to WebSocket button events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._unique_id}_{CONNECTION_STATUS}",
                self._async_update_connection_state,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._unique_id}_{WebsocketNotification.BUTTON}_{self._button_type}",
                self._async_handle_event,
            )
        )


class BeoRemoteKeyEvent(BeoEvent):
    """Event class for Beoremote One key events."""

    _attr_event_types = BEO_REMOTE_KEY_EVENTS

    def __init__(
        self,
        config_entry: BeoConfigEntry,
        remote: PairedRemote,
        key_type: str,
    ) -> None:
        """Initialize Beoremote One key."""
        super().__init__(config_entry)

        if TYPE_CHECKING:
            assert remote.serial_number

        self._attr_unique_id = f"{remote.serial_number}_{self._unique_id}_{key_type}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{remote.serial_number}_{self._unique_id}")},
            name=f"{BeoModel.BEOREMOTE_ONE}-{remote.serial_number}-{self._unique_id}",
            model=BeoModel.BEOREMOTE_ONE,
            serial_number=remote.serial_number,
            sw_version=remote.app_version,
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, self._unique_id),
        )

        # Make the native key name Home Assistant compatible
        self._attr_translation_key = key_type.lower().replace("/", "_")

        self._key_type = key_type

    async def async_added_to_hass(self) -> None:
        """Listen to WebSocket Beoremote One key events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._unique_id}_{CONNECTION_STATUS}",
                self._async_update_connection_state,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._unique_id}_{WebsocketNotification.BEO_REMOTE_BUTTON}_{self._key_type}",
                self._async_handle_event,
            )
        )
