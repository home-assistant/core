"""Support for Tractive switches."""

from dataclasses import dataclass
from typing import Any, Literal, override

from aiotractive import Trackable
from aiotractive.exceptions import TractiveError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_BUZZER, ATTR_LED, ATTR_LIVE_TRACKING, DOMAIN
from .coordinator import TractiveConfigEntry, TractiveCoordinator
from .entity import TractiveEntity


@dataclass(frozen=True, kw_only=True)
class TractiveSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Tractive switch entities."""

    method: Literal["async_set_buzzer", "async_set_led", "async_set_live_tracking"]


SWITCH_TYPES: tuple[TractiveSwitchEntityDescription, ...] = (
    TractiveSwitchEntityDescription(
        key=ATTR_BUZZER,
        translation_key="tracker_buzzer",
        method="async_set_buzzer",
        entity_category=EntityCategory.CONFIG,
    ),
    TractiveSwitchEntityDescription(
        key=ATTR_LED,
        translation_key="tracker_led",
        method="async_set_led",
        entity_category=EntityCategory.CONFIG,
    ),
    TractiveSwitchEntityDescription(
        key=ATTR_LIVE_TRACKING,
        translation_key="live_tracking",
        method="async_set_live_tracking",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TractiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tractive switches."""
    coordinator = entry.runtime_data

    async_add_entities(
        TractiveSwitch(coordinator, trackable, description)
        for description in SWITCH_TYPES
        for trackable in coordinator.trackables
    )


class TractiveSwitch(TractiveEntity, SwitchEntity):
    """Tractive switch."""

    entity_description: TractiveSwitchEntityDescription

    def __init__(
        self,
        coordinator: TractiveCoordinator,
        trackable: Trackable,
        description: TractiveSwitchEntityDescription,
    ) -> None:
        """Initialize switch entity."""
        super().__init__(coordinator, trackable)
        self._attr_unique_id = f"{trackable.pet_id}_{description.key}"
        self._tracker = coordinator.client.tracker(trackable.tracker_id)
        self._method = getattr(self, description.method)
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        is_on: bool | None = getattr(self._tracker_status, self.entity_description.key)
        return is_on

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and not self._tracker_status.power_saving_zone

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on a switch."""
        try:
            await self._method(True)
        except TractiveError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_turn_on",
                translation_placeholders={"entity": self.entity_id},
            ) from error
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off a switch."""
        try:
            await self._method(False)
        except TractiveError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_turn_off",
                translation_placeholders={"entity": self.entity_id},
            ) from error
        self.async_write_ha_state()

    async def async_set_buzzer(self, active: bool) -> dict[str, Any]:
        """Set the buzzer on/off."""
        return await self._tracker.set_buzzer_active(active)

    async def async_set_led(self, active: bool) -> dict[str, Any]:
        """Set the LED on/off."""
        return await self._tracker.set_led_active(active)

    async def async_set_live_tracking(self, active: bool) -> dict[str, Any]:
        """Set the live tracking on/off."""
        return await self._tracker.set_live_tracking_active(active)
