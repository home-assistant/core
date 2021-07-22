"""Support for setting the Transmission BitTorrent client Turtle Mode."""
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import TransmissionClientCoordinator
from .const import DOMAIN, SWITCH_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission switch."""

    tm_client: TransmissionClientCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for switch_type, switch_name in SWITCH_TYPES.items():
        entities.append(TransmissionSwitch(tm_client, switch_type, switch_name))

    async_add_entities(entities)


class TransmissionSwitch(CoordinatorEntity, ToggleEntity):
    """Representation of a Transmission switch."""

    coordinator: TransmissionClientCoordinator

    def __init__(
        self,
        coordinator: TransmissionClientCoordinator,
        switch_type: str,
        switch_name: str,
    ) -> None:
        """Initialize the Transmission switch."""
        super().__init__(coordinator)
        client_name = self.coordinator.config_entry.data[CONF_NAME]
        self._attr_name = f"{client_name} {switch_name}"
        self.type = switch_type
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.data[CONF_HOST]}-{self._attr_name}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.data[CONF_HOST])},
            "default_name": client_name,
            "entry_type": "service",
        }

    @property
    def is_on(self) -> bool:
        """Return the state of the entity."""
        if self.type == "on_off":
            return self.coordinator.data.activeTorrentCount > 0
        if self.type == "turtle_mode":
            return self.coordinator.data.alt_speed_enabled
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self.type == "on_off":
            _LOGGER.debug("Starting all torrents")
            await self.hass.async_add_executor_job(
                self.coordinator.tm_data.start_torrents
            )
        elif self.type == "turtle_mode":
            _LOGGER.debug("Turning Turtle Mode of Transmission on")
            await self.hass.async_add_executor_job(
                self.coordinator.tm_data.set_alt_speed_enabled, True
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self.type == "on_off":
            _LOGGER.debug("Stopping all torrents")
            await self.hass.async_add_executor_job(
                self.coordinator.tm_data.stop_torrents
            )
        if self.type == "turtle_mode":
            _LOGGER.debug("Turning Turtle Mode of Transmission off")
            await self.hass.async_add_executor_job(
                self.coordinator.tm_data.set_alt_speed_enabled, False
            )
        await self.coordinator.async_request_refresh()
