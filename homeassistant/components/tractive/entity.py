"""A entity class for Tractive integration."""

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import TractiveClient
from .const import DOMAIN, SERVER_UNAVAILABLE


class TractiveEntity(Entity):
    """Tractive entity class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        client: TractiveClient,
        trackable: dict[str, Any],
        tracker_details: dict[str, Any],
        dispatcher_signal: str,
        hardware_entity: bool = True,
    ) -> None:
        """Initialize tracker entity."""
        if hardware_entity:
            self._attr_device_info = DeviceInfo(
                configuration_url="https://my.tractive.com/",
                identifiers={(DOMAIN, tracker_details["_id"])},
                translation_key="tracker",
                translation_placeholders={"id": tracker_details["_id"]},
                manufacturer="Tractive GmbH",
                sw_version=tracker_details["fw_version"],
                model_id=tracker_details["model_number"],
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, trackable["_id"])},
                name=trackable["details"]["name"],
                via_device=(DOMAIN, tracker_details["_id"]),
                entry_type=DeviceEntryType.SERVICE,
            )

        self._user_id = client.user_id
        self._tracker_id = tracker_details["_id"]
        self._client = client
        self._dispatcher_signal = dispatcher_signal

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        if not self._client.subscribed:
            self._client.subscribe()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._dispatcher_signal,
                self.handle_status_update,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_UNAVAILABLE}-{self._user_id}",
                self.handle_server_unavailable,
            )
        )

    @callback
    def handle_status_update(self, event: dict[str, Any]) -> None:
        """Handle status update."""
        self._attr_available = event[self.entity_description.key] is not None
        self.async_write_ha_state()

    @callback
    def handle_server_unavailable(self) -> None:
        """Handle server unavailable."""
        self._attr_available = False
        self.async_write_ha_state()
