"""Support for interface with a Gree climate systems."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from greeclimate.device import Device, HorizontalSwing, VerticalSwing

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DISPATCH_DEVICE_DISCOVERED
from .coordinator import GreeConfigEntry
from .entity import DeviceDataUpdateCoordinator, GreeEntity


@dataclass(kw_only=True, frozen=True)
class GreeSelectEntityDescription(SelectEntityDescription):
    """Describes a Gree select entity."""

    get_value_fn: Callable[[Device], str | None]
    set_value_fn: Callable[[Device, str], None]


def _get_horizontal_swing(device: Device) -> str | None:
    try:
        return HorizontalSwing(device.horizontal_swing).name
    except ValueError:
        return None


def _set_horizontal_swing(device: Device, option: str) -> None:
    device.horizontal_swing = HorizontalSwing[option]


def _get_vertical_swing(device: Device) -> str | None:
    try:
        return VerticalSwing(device.vertical_swing).name
    except ValueError:
        return None


def _set_vertical_swing(device: Device, option: str) -> None:
    device.vertical_swing = VerticalSwing[option]


GREE_SELECTS: tuple[GreeSelectEntityDescription, ...] = (
    GreeSelectEntityDescription(
        key="Horizontal Swing",
        translation_key="horizontal_swing",
        options=[e.name for e in sorted(HorizontalSwing, key=lambda x: x.value)],
        get_value_fn=_get_horizontal_swing,
        set_value_fn=_set_horizontal_swing,
    ),
    GreeSelectEntityDescription(
        key="Vertical Swing",
        translation_key="vertical_swing",
        options=[e.name for e in sorted(VerticalSwing, key=lambda x: x.value)],
        get_value_fn=_get_vertical_swing,
        set_value_fn=_set_vertical_swing,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Gree HVAC device from a config entry."""

    @callback
    def init_device(coordinator: DeviceDataUpdateCoordinator) -> None:
        """Register the device."""
        async_add_entities(
            GreeSelect(coordinator=coordinator, description=description)
            for description in GREE_SELECTS
        )

    for coordinator in entry.runtime_data.coordinators:
        init_device(coordinator)

    entry.async_on_unload(
        async_dispatcher_connect(hass, DISPATCH_DEVICE_DISCOVERED, init_device)
    )


class GreeSelect(GreeEntity, SelectEntity):
    """Generic Gree select entity."""

    entity_description: GreeSelectEntityDescription

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        description: GreeSelectEntityDescription,
    ) -> None:
        """Initialize the Gree device."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return self.entity_description.get_value_fn(self.coordinator.device)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.entity_description.set_value_fn(self.coordinator.device, option)
        await self.coordinator.push_state_update()
        self.async_write_ha_state()
