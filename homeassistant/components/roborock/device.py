"""Support for Roborock device base class."""

from typing import Any

from roborock.command_cache import CacheableAttribute
from roborock.containers import Consumable, Status
from roborock.exceptions import RoborockException
from roborock.roborock_message import RoborockDataProtocol
from roborock.roborock_typing import RoborockCommand
from roborock.version_1_apis.roborock_client_v1 import AttributeCache, RoborockClientV1
from roborock.version_1_apis.roborock_mqtt_client_v1 import RoborockMqttClientV1

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator


class RoborockEntity(Entity):
    """Representation of a base Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        device_info: DeviceInfo,
        api: RoborockClientV1,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._api = api

    @property
    def api(self) -> RoborockClientV1:
        """Returns the api."""
        return self._api

    def get_cache(self, attribute: CacheableAttribute) -> AttributeCache:
        """Get an item from the api cache."""
        return self._api.cache[attribute]

    async def send(
        self,
        command: RoborockCommand | str,
        params: dict[str, Any] | list[Any] | int | None = None,
    ) -> dict:
        """Send a command to a vacuum cleaner."""
        try:
            response: dict = await self._api.send_command(command, params)
        except RoborockException as err:
            if isinstance(command, RoborockCommand):
                command_name = command.name
            else:
                command_name = command
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": command_name,
                },
            ) from err
        return response


class RoborockCoordinatedEntity(
    RoborockEntity, CoordinatorEntity[RoborockDataUpdateCoordinator]
):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        listener_request: list[RoborockDataProtocol]
        | RoborockDataProtocol
        | None = None,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        RoborockEntity.__init__(
            self,
            unique_id=unique_id,
            device_info=coordinator.device_info,
            api=coordinator.api,
        )
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        self._attr_unique_id = unique_id
        if isinstance(listener_request, RoborockDataProtocol):
            listener_request = [listener_request]
        self.listener_requests = listener_request or []

    async def async_added_to_hass(self) -> None:
        """Add listeners when the device is added to hass."""
        await super().async_added_to_hass()
        for listener_request in self.listener_requests:
            self.api.add_listener(
                listener_request, self._update_from_listener, cache=self.api.cache
            )

    async def async_will_remove_from_hass(self) -> None:
        """Remove listeners when the device is removed from hass."""
        for listener_request in self.listener_requests:
            self.api.remove_listener(listener_request, self._update_from_listener)
        await super().async_will_remove_from_hass()

    @property
    def _device_status(self) -> Status:
        """Return the status of the device."""
        data = self.coordinator.data
        return data.status

    @property
    def cloud_api(self) -> RoborockMqttClientV1:
        """Return the cloud api."""
        return self.coordinator.cloud_api

    async def send(
        self,
        command: RoborockCommand | str,
        params: dict[str, Any] | list[Any] | int | None = None,
    ) -> dict:
        """Overloads normal send command but refreshes coordinator."""
        res = await super().send(command, params)
        await self.coordinator.async_refresh()
        return res

    def _update_from_listener(self, value: Status | Consumable) -> None:
        """Update the status or consumable data from a listener and then write the new entity state."""
        if isinstance(value, Status):
            self.coordinator.roborock_device_info.props.status = value
        else:
            self.coordinator.roborock_device_info.props.consumable = value
        self.coordinator.data = self.coordinator.roborock_device_info.props
        self.schedule_update_ha_state()
