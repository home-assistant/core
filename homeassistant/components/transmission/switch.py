"""Support for setting the Transmission BitTorrent client Turtle Mode."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TransmissionDataUpdateCoordinator

_LOGGING = logging.getLogger(__name__)

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(key="on_off", translation_key="on_off"),
    SwitchEntityDescription(key="turtle_mode", translation_key="turtle_mode"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission switch."""

    coordinator: TransmissionDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        TransmissionSwitch(coordinator, description) for description in SWITCH_TYPES
    )


class TransmissionSwitch(
    CoordinatorEntity[TransmissionDataUpdateCoordinator], SwitchEntity
):
    """Representation of a Transmission switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TransmissionDataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the Transmission switch."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Transmission",
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        active = None
        if self.entity_description.key == "on_off":
            active = self.coordinator.data.active_torrent_count > 0
        elif self.entity_description.key == "turtle_mode":
            active = self.coordinator.get_alt_speed_enabled()

        return bool(active)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self.entity_description.key == "on_off":
            _LOGGING.debug("Starting all torrents")
            await self.hass.async_add_executor_job(self.coordinator.start_torrents)
        elif self.entity_description.key == "turtle_mode":
            _LOGGING.debug("Turning Turtle Mode of Transmission on")
            await self.hass.async_add_executor_job(
                self.coordinator.set_alt_speed_enabled, True
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self.entity_description.key == "on_off":
            _LOGGING.debug("Stopping all torrents")
            await self.hass.async_add_executor_job(self.coordinator.stop_torrents)
        if self.entity_description.key == "turtle_mode":
            _LOGGING.debug("Turning Turtle Mode of Transmission off")
            await self.hass.async_add_executor_job(
                self.coordinator.set_alt_speed_enabled, False
            )
        await self.coordinator.async_request_refresh()
