"""Support for interacting with Snapcast clients."""

from __future__ import annotations

import logging

from snapcast.control.stream import Snapstream

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STREAM_PREFIX, STREAM_SUFFIX
from .coordinator import SnapcastUpdateCoordinator
from .entity import SnapcastCoordinatorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the snapcast config entry."""

    # Fetch coordinator from global data
    coordinator: SnapcastUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create an ID for the Snapserver
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    host_id = f"{host}:{port}"

    _known_stream_ids: set[str] = set()

    @callback
    def _check_entities() -> None:
        nonlocal _known_stream_ids

        def _update_known_ids(known_ids, ids) -> tuple[set[str], set[str]]:
            ids_to_add = ids - known_ids
            ids_to_remove = known_ids - ids

            # Update known IDs
            known_ids.difference_update(ids_to_remove)
            known_ids.update(ids_to_add)

            return ids_to_add, ids_to_remove

        stream_ids = {s.identifier for s in coordinator.server.streams}
        streams_to_add, streams_to_remove = _update_known_ids(
            _known_stream_ids, stream_ids
        )

        # Exit early if no changes
        if not (streams_to_add | streams_to_remove):
            return

        _LOGGER.debug(
            "New streams: %s",
            str([coordinator.server.stream(s).friendly_name for s in streams_to_add]),
        )
        _LOGGER.debug(
            "Remove stream IDs: %s",
            str(list(streams_to_remove)),
        )

        # Add new entities
        async_add_entities(
            [
                SnapcastStreamDevice(
                    coordinator, coordinator.server.stream(stream_id), host_id
                )
                for stream_id in streams_to_add
            ]
        )

        # Remove stale entities
        entity_registry = er.async_get(hass)
        for stream_id in streams_to_remove:
            if entity_id := entity_registry.async_get_entity_id(
                BINARY_SENSOR_DOMAIN,
                DOMAIN,
                SnapcastStreamDevice.get_unique_id(host_id, stream_id),
            ):
                entity_registry.async_remove(entity_id)

    coordinator.async_add_listener(_check_entities)
    _check_entities()


class SnapcastStreamDevice(SnapcastCoordinatorEntity, BinarySensorEntity):
    """Class representing a Snapcast stream."""

    _attr_is_on = False
    _attr_device_class = BinarySensorDeviceClass.SOUND
    _device: Snapstream

    # _attr_supported_features = (
    #     MediaPlayerEntityFeature.VOLUME_MUTE
    #     | MediaPlayerEntityFeature.VOLUME_SET
    #     | MediaPlayerEntityFeature.SELECT_SOURCE
    # )

    def __init__(
        self,
        coordinator: SnapcastUpdateCoordinator,
        device: Snapstream,
        host_id: str,
    ) -> None:
        """Initialize the base device."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = self.get_unique_id(host_id, device.identifier)
        self.entity_description = BinarySensorEntityDescription(
            key=self._attr_unique_id,
            device_class=self._attr_device_class,
            has_entity_name=True,
            name=self.name,
        )

    def update_stream(self, stream: Snapstream) -> bool | None:
        """Return true if the binary sensor is on."""
        self._attr_is_on = self._device.status == "playing"
        self.async_schedule_update_ha_state()
        return self._attr_is_on

    @classmethod
    def get_unique_id(cls, host, id) -> str:
        """Build a unique ID."""
        return f"{STREAM_PREFIX}{host}_{id}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""
        await super().async_added_to_hass()
        self._device.set_callback(self.update_stream)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        self._device.set_callback(None)

    @property
    def identifier(self) -> str:
        """Return the snapcast identifier."""
        return self._device.identifier

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{self._device.friendly_name} {STREAM_SUFFIX}"
