"""Support for setting the Transmission BitTorrent client Turtle Mode."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TransmissionConfigEntry, TransmissionDataUpdateCoordinator
from .entity import TransmissionEntity

PARALLEL_UPDATES = 0
AFTER_WRITE_SLEEP = 2


@dataclass(frozen=True, kw_only=True)
class TransmissionSwitchEntityDescription(SwitchEntityDescription):
    """Entity description class for Transmission switches."""

    is_on_func: Callable[[TransmissionDataUpdateCoordinator], bool | None]
    on_func: Callable[[TransmissionDataUpdateCoordinator], None]
    off_func: Callable[[TransmissionDataUpdateCoordinator], None]


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
    config_entry: TransmissionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Transmission switch."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        TransmissionSwitch(coordinator, description) for description in SWITCH_TYPES
    )


class TransmissionSwitch(TransmissionEntity, SwitchEntity):
    """Representation of a Transmission switch."""

    entity_description: TransmissionSwitchEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return bool(self.entity_description.is_on_func(self.coordinator))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.hass.async_add_executor_job(
            self.entity_description.on_func, self.coordinator
        )
        await asyncio.sleep(AFTER_WRITE_SLEEP)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.hass.async_add_executor_job(
            self.entity_description.off_func, self.coordinator
        )
        await asyncio.sleep(AFTER_WRITE_SLEEP)
        await self.coordinator.async_request_refresh()
