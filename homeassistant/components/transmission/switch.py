"""Support for setting the Transmission BitTorrent client Turtle Mode."""
from collections.abc import Callable
from dataclasses import dataclass
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


@dataclass(frozen=True)
class TransmissionSwitchEntityDescriptionMixin:
    """Mixin for required keys."""

    is_on_func: Callable[[TransmissionDataUpdateCoordinator], bool | None]
    on_func: Callable[[TransmissionDataUpdateCoordinator], None]
    off_func: Callable[[TransmissionDataUpdateCoordinator], None]


@dataclass(frozen=True)
class TransmissionSwitchEntityDescription(
    SwitchEntityDescription, TransmissionSwitchEntityDescriptionMixin
):
    """Entity description class for Transmission switches."""


SWITCH_TYPES: tuple[TransmissionSwitchEntityDescription, ...] = (
    TransmissionSwitchEntityDescription(
        key="on_off",
        translation_key="on_off",
        is_on_func=lambda coordinator: coordinator.data.active_torrent_count > 0,
        on_func=lambda coordinator: coordinator.start_torrents(),
        off_func=lambda coordinator: coordinator.stop_torrents(),
    ),
    TransmissionSwitchEntityDescription(
        key="turtle_mode",
        translation_key="turtle_mode",
        is_on_func=lambda coordinator: coordinator.get_alt_speed_enabled(),
        on_func=lambda coordinator: coordinator.set_alt_speed_enabled(True),
        off_func=lambda coordinator: coordinator.set_alt_speed_enabled(False),
    ),
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

    entity_description: TransmissionSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TransmissionDataUpdateCoordinator,
        entity_description: TransmissionSwitchEntityDescription,
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
        return bool(self.entity_description.is_on_func(self.coordinator))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.hass.async_add_executor_job(
            self.entity_description.on_func, self.coordinator
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.hass.async_add_executor_job(
            self.entity_description.off_func, self.coordinator
        )
        await self.coordinator.async_request_refresh()
