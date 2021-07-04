"""The motionEye integration."""
from __future__ import annotations

import datetime
import logging
from types import MappingProxyType
from typing import Any, Callable

from motioneye_client.client import MotionEyeClient
from motioneye_client.const import KEY_NAME

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import Event, async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import MotionEyeEntity, listen_for_new_cameras
from .const import (
    CONF_CLIENT,
    CONF_COORDINATOR,
    CONF_EVENT_DURATION,
    DEFAULT_EVENT_DURATION,
    DOMAIN,
    EVENT_FILE_STORED,
    EVENT_MOTION_DETECTED,
    TYPE_MOTIONEYE_FILE_STORED_BINARY_SENSOR,
    TYPE_MOTIONEYE_MOTION_BINARY_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up motionEye from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    @callback
    def camera_add(camera: dict[str, Any]) -> None:
        """Add a new motionEye camera."""
        args = [
            entry.entry_id,
            camera,
            entry_data[CONF_CLIENT],
            entry_data[CONF_COORDINATOR],
            entry.options,
        ]
        async_add_entities(
            [
                MotionEyeMotionBinarySensor(*args),
                MotionEyeFileStoredBinarySensor(*args),
            ]
        )

    listen_for_new_cameras(hass, entry, camera_add)


class MotionEyeEventBinarySensor(MotionEyeEntity, BinarySensorEntity):
    """Base class for motionEye event-based binary sensors."""

    def __init__(
        self,
        config_entry_id: str,
        type_name: str,
        camera: dict[str, Any],
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
        options: MappingProxyType[str, Any],
        event: str,
        friendly_name: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            config_entry_id, type_name, camera, client, coordinator, options
        )
        self._state = False
        self._event = event
        self._friendly_name = friendly_name
        self._timer_unsub: Callable | None = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        camera_name = self._camera[KEY_NAME] if self._camera else ""
        return f"{camera_name} {self._friendly_name}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state

    @callback
    def _cancel_timer(self) -> None:
        """Cancel the internal state timer."""
        if self._timer_unsub is not None:
            self._timer_unsub()
            self._timer_unsub = None

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup prior to removal from hass."""
        self._cancel_timer()
        await super().async_will_remove_from_hass()

    async def async_added_to_hass(self) -> None:
        """Register event listeners when added to hass."""

        device_registry = dr.async_get(self.hass)

        @callback
        def handle_event(event: Event) -> None:
            """Handle an event."""

            @callback
            def turn_off(_: datetime.datetime) -> None:
                """Turn the state off."""
                self._state = False
                self.async_write_ha_state()
                self._timer_unsub = None

            if CONF_DEVICE_ID in event.data:
                device = device_registry.async_get(event.data[CONF_DEVICE_ID])
                if device and self._device_identifier in device.identifiers:
                    self._cancel_timer()
                    self._timer_unsub = async_call_later(
                        self.hass,
                        self._options.get(CONF_EVENT_DURATION, DEFAULT_EVENT_DURATION),
                        turn_off,
                    )
                    self._state = True
                    self.async_write_ha_state()

        self.hass.bus.async_listen(f"{DOMAIN}.{self._event}", handle_event)
        await super().async_added_to_hass()


class MotionEyeMotionBinarySensor(MotionEyeEventBinarySensor):
    """Binary sensor to show motion detected."""

    def __init__(
        self,
        config_entry_id: str,
        camera: dict[str, Any],
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
        options: MappingProxyType[str, Any],
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            config_entry_id,
            TYPE_MOTIONEYE_MOTION_BINARY_SENSOR,
            camera,
            client,
            coordinator,
            options,
            EVENT_MOTION_DETECTED,
            "Motion",
        )

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return DEVICE_CLASS_MOTION


class MotionEyeFileStoredBinarySensor(MotionEyeEventBinarySensor):
    """Binary sensor to show files stored."""

    def __init__(
        self,
        config_entry_id: str,
        camera: dict[str, Any],
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
        options: MappingProxyType[str, Any],
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            config_entry_id,
            TYPE_MOTIONEYE_FILE_STORED_BINARY_SENSOR,
            camera,
            client,
            coordinator,
            options,
            EVENT_FILE_STORED,
            "File Stored",
        )
