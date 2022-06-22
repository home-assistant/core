"""Support for setting the Transmission BitTorrent client Turtle Mode."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SWITCH_TYPES
from .coordinator import TransmissionDataUpdateCoordinator

_LOGGING = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission switch."""

    tm_client: TransmissionDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    name = config_entry.data[CONF_NAME]

    entities = []
    for switch_type, switch_name in SWITCH_TYPES.items():
        entities.append(TransmissionSwitch(switch_type, switch_name, tm_client, name))

    async_add_entities(entities)


class TransmissionSwitch(
    CoordinatorEntity[TransmissionDataUpdateCoordinator], SwitchEntity
):
    """Representation of a Transmission switch."""

    def __init__(
        self,
        switch_type,
        switch_name,
        tm_client,
        name,
    ):
        """Initialize the Transmission switch."""
        super().__init__(tm_client)
        self._attr_name = f"{name} {switch_name}"
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.data[CONF_HOST]}-{self._attr_name}"
        )
        self.type = switch_type
        if self.type == "on_off":
            return self.coordinator.data.activeTorrentCount > 0
        if self.type == "turtle_mode":
            return self.coordinator.data.alt_speed_enabled
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self.type == "on_off":
            _LOGGING.debug("Starting all torrents")
            await self.hass.async_add_executor_job(self.coordinator.api.start_torrents)
        elif self.type == "turtle_mode":
            _LOGGING.debug("Turning Turtle Mode of Transmission on")
            await self.hass.async_add_executor_job(
                self.coordinator.api.set_alt_speed_enabled, True
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self.type == "on_off":
            _LOGGING.debug("Stopping all torrents")
            await self.hass.async_add_executor_job(self.coordinator.api.stop_torrents)
        if self.type == "turtle_mode":
            _LOGGING.debug("Turning Turtle Mode of Transmission off")
            await self.hass.async_add_executor_job(
                self.coordinator.api.set_alt_speed_enabled, False
            )
        await self.coordinator.async_request_refresh()
