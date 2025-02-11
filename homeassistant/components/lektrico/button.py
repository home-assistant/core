"""Support for Lektrico buttons."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from lektricowifi import Device

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import ATTR_SERIAL_NUMBER, CONF_TYPE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LektricoConfigEntry, LektricoDeviceDataUpdateCoordinator
from .entity import LektricoEntity


@dataclass(frozen=True, kw_only=True)
class LektricoButtonEntityDescription(ButtonEntityDescription):
    """Describes Lektrico button entity."""

    press_fn: Callable[[Device], Coroutine[Any, Any, dict[Any, Any]]]


BUTTONS_FOR_CHARGERS: tuple[LektricoButtonEntityDescription, ...] = (
    LektricoButtonEntityDescription(
        key="charge_start",
        translation_key="charge_start",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda device: device.send_charge_start(),
    ),
    LektricoButtonEntityDescription(
        key="charge_stop",
        translation_key="charge_stop",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda device: device.send_charge_stop(),
    ),
    LektricoButtonEntityDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda device: device.send_reset(),
    ),
)

BUTTONS_FOR_LB_DEVICES: tuple[LektricoButtonEntityDescription, ...] = (
    LektricoButtonEntityDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda device: device.send_reset(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LektricoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    coordinator = entry.runtime_data

    buttons_to_be_used: tuple[LektricoButtonEntityDescription, ...]
    if coordinator.device_type in (Device.TYPE_1P7K, Device.TYPE_3P22K):
        buttons_to_be_used = BUTTONS_FOR_CHARGERS
    else:
        buttons_to_be_used = BUTTONS_FOR_LB_DEVICES

    async_add_entities(
        LektricoButton(
            description,
            coordinator,
            f"{entry.data[CONF_TYPE]}_{entry.data[ATTR_SERIAL_NUMBER]}",
        )
        for description in buttons_to_be_used
    )


class LektricoButton(LektricoEntity, ButtonEntity):
    """Defines an Lektrico button."""

    entity_description: LektricoButtonEntityDescription

    def __init__(
        self,
        description: LektricoButtonEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize Lektrico button."""
        super().__init__(coordinator, device_name)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}-{description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.coordinator.device)
