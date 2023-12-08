"""Fully Kiosk Browser switch."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fullykiosk import FullyKiosk

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity


@dataclass
class FullySwitchEntityDescriptionMixin:
    """Fully Kiosk Browser switch entity description mixin."""

    on_action: Callable[[FullyKiosk], Any]
    off_action: Callable[[FullyKiosk], Any]
    is_on_fn: Callable[[dict[str, Any]], Any]
    mqtt_on_event: str | None
    mqtt_off_event: str | None


@dataclass
class FullySwitchEntityDescription(
    SwitchEntityDescription, FullySwitchEntityDescriptionMixin
):
    """Fully Kiosk Browser switch entity description."""


SWITCHES: tuple[FullySwitchEntityDescription, ...] = (
    FullySwitchEntityDescription(
        key="screensaver",
        translation_key="screensaver",
        on_action=lambda fully: fully.startScreensaver(),
        off_action=lambda fully: fully.stopScreensaver(),
        is_on_fn=lambda data: data.get("isInScreensaver"),
        mqtt_on_event="onScreensaverStart",
        mqtt_off_event="onScreensaverStop",
    ),
    FullySwitchEntityDescription(
        key="maintenance",
        translation_key="maintenance",
        entity_category=EntityCategory.CONFIG,
        on_action=lambda fully: fully.enableLockedMode(),
        off_action=lambda fully: fully.disableLockedMode(),
        is_on_fn=lambda data: data.get("maintenanceMode"),
        mqtt_on_event=None,
        mqtt_off_event=None,
    ),
    FullySwitchEntityDescription(
        key="kiosk",
        translation_key="kiosk",
        entity_category=EntityCategory.CONFIG,
        on_action=lambda fully: fully.lockKiosk(),
        off_action=lambda fully: fully.unlockKiosk(),
        is_on_fn=lambda data: data.get("kioskLocked"),
        mqtt_on_event=None,
        mqtt_off_event=None,
    ),
    FullySwitchEntityDescription(
        key="motion-detection",
        translation_key="motion_detection",
        entity_category=EntityCategory.CONFIG,
        on_action=lambda fully: fully.enableMotionDetection(),
        off_action=lambda fully: fully.disableMotionDetection(),
        is_on_fn=lambda data: data["settings"].get("motionDetection"),
        mqtt_on_event=None,
        mqtt_off_event=None,
    ),
    FullySwitchEntityDescription(
        key="screenOn",
        translation_key="screen_on",
        on_action=lambda fully: fully.screenOn(),
        off_action=lambda fully: fully.screenOff(),
        is_on_fn=lambda data: data.get("screenOn"),
        mqtt_on_event="screenOn",
        mqtt_off_event="screenOff",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser switch."""
    coordinator: FullyKioskDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        FullySwitchEntity(coordinator, description) for description in SWITCHES
    )


class FullySwitchEntity(FullyKioskEntity, SwitchEntity):
    """Fully Kiosk Browser switch entity."""

    entity_description: FullySwitchEntityDescription

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        description: FullySwitchEntityDescription,
    ) -> None:
        """Initialize the Fully Kiosk Browser switch entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data['deviceID']}-{description.key}"
        self._turned_on_subscription: CALLBACK_TYPE | None = None
        self._turned_off_subscription: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        description = self.entity_description
        self._turned_on_subscription = await self.mqtt_subscribe(
            description.mqtt_off_event, self._turn_off
        )
        self._turned_off_subscription = await self.mqtt_subscribe(
            description.mqtt_on_event, self._turn_on
        )

    async def async_will_remove_from_hass(self) -> None:
        """Close MQTT subscriptions when removed."""
        await super().async_will_remove_from_hass()
        if self._turned_off_subscription is not None:
            self._turned_off_subscription()
        if self._turned_on_subscription is not None:
            self._turned_on_subscription()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.on_action(self.coordinator.fully)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.off_action(self.coordinator.fully)
        await self.coordinator.async_refresh()

    def _turn_off(self, **kwargs: Any) -> None:
        """Optimistically turn off."""
        self._attr_is_on = False
        self.async_write_ha_state()

    def _turn_on(self, **kwargs: Any) -> None:
        """Optimistically turn on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = bool(self.entity_description.is_on_fn(self.coordinator.data))
        self.async_write_ha_state()
