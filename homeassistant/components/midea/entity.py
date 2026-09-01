"""Base entity for Midea."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, override

from midealocal.device import MideaDevice
from midealocal.exceptions import MideaLocalError

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN, LOGGER
from .device_catalog import MIDEA_DEVICE_NAMES

type MideaConfigEntry = ConfigEntry[MideaDevice]


@contextmanager
def midea_api_call() -> Generator[None]:
    """Translate midealocal device-communication errors into HomeAssistantError."""
    try:
        yield
    except MideaLocalError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_communication_error",
            translation_placeholders={"error": str(err)},
        ) from err


class MideaEntity(Entity):
    """Base Midea entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, device: MideaDevice, entity_description: EntityDescription
    ) -> None:
        """Initialize Midea base entity."""
        self._device = device
        self._unique_id = f"{self._device.device_id}_{entity_description.key}"
        self._device_name = self._device.name
        self.entity_description = entity_description

    @override
    async def async_added_to_hass(self) -> None:
        """Register update callback when entity is added."""
        self._device.register_update(self.update_state)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister update callback when entity is removed."""
        self._device.unregister_update(self.update_state)

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        device_info = DeviceInfo(
            manufacturer="Midea",
            # Map the device type (numeric ID) to a human-readable model name.
            model=MIDEA_DEVICE_NAMES.get(self._device.device_type),
            identifiers={(DOMAIN, str(self._device.device_id))},
            name=self._device_name,
            model_id=self._device.device_type.name,
            hw_version=str(self._device.model),
        )
        if mac := self._device.mac:
            device_info["connections"] = {(CONNECTION_NETWORK_MAC, mac)}
        if serial_number := self._device.serial_number:
            device_info["serial_number"] = serial_number

        return device_info

    @property
    @override
    def unique_id(self) -> str:
        """Return entity unique id."""
        return self._unique_id

    @property
    @override
    def available(self) -> bool:
        """Return entity availability."""
        return bool(self._device.available)

    def update_state(self, status: Any) -> None:
        """Update entity state."""
        if self.hass.is_stopping:
            LOGGER.debug(
                "MideaEntity update_state for %s [%s] with status %s: HASS is stopping",
                self.name,
                type(self),
                status,
            )
            return

        self.schedule_update_ha_state()
