from __future__ import annotations

import logging
from typing import Optional, List

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NAME
from .notificationdevice import effortlesshomenotificationdevice

_LOGGER = logging.getLogger(__name__)

class eh_personSensor(Entity):
    """A sensor-like representation of an EffortlessHome Person with tracking and notifications."""

    def __init__(
        self,
        hass: HomeAssistant,
        email: str,
        token: str,
        device_name: str,
        platform_name: str,
    ):
        self.hass = hass
        self._email = email
        self._attr_name = email
        self._attr_unique_id = f"effortlesshome_person_{email.lower().replace('@', '_').replace('.', '_')}"
        self._attr_icon = "mdi:account"
        self._attr_extra_state_attributes = {}
        self._attr_should_poll = False

        self._local_tracker_entity_id: Optional[str] = None
        self._remote_tracker_entity_id: Optional[str] = None

        # Notification devices
        self._notification_devices: List[effortlesshomenotificationdevice] = []

        if not token:
            _LOGGER.warning("[eh_personSensor] Missing token for notification registration.")
        else:
            existing = next(
                (d for d in self._notification_devices if d.unique_id == f"effortlesshome_notify_{device_name}"), None
            )
            if existing:
                _LOGGER.info("[eh_personSensor] Notification device %s already exists for %s", token, self._email)
            else:
                device = effortlesshomenotificationdevice(self.hass, token, device_name, platform_name)
                self._notification_devices.append(device)
                #self.update_ha_state()
                _LOGGER.info("[eh_personSensor] Added notification device for %s: %s", self._email, platform_name)

        # Device registry
        self._device_registry = async_get_dev_reg(hass)
        self._device_id = None

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def icon(self) -> str:
        return "mdi:account-group"

    @property
    def state(self) -> str:
        return self._email

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._email      

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def email(self) -> str:
        """Return the value"""
        return self._email

    @property
    def remote_tracker_entity(self) -> str:
        """Return the value"""
        return self._remote_tracker_entity_id

    @property
    def local_tracker_entity(self) -> str:
        """Return the value"""
        return self._local_tracker_entity_id     

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        return {
            "email": self._email,
            "local_tracker": self._local_tracker_entity_id,
            "remote_tracker": self._remote_tracker_entity_id,
            "notification_devices": [d.unique_id for d in self._notification_devices],
        }

    async def async_set_local_tracker(self, entity_id: str):
        """Link a local device_tracker entity."""
        self._local_tracker_entity_id = entity_id
        _LOGGER.info("[eh_personSensor] Linked local tracker for %s: %s", self._email, entity_id)
        await self.async_update_ha_state()

    async def async_set_remote_tracker(self, entity_id: str):
        """Link a remote (EffortlessHome cloud) device_tracker entity."""
        self._remote_tracker_entity_id = entity_id
        _LOGGER.info("[eh_personSensor] Linked remote tracker for %s: %s", self._email, entity_id)
        await self.async_update_ha_state()

