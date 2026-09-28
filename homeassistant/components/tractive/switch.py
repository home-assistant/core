"""Support for Tractive switches."""

from dataclasses import dataclass
import logging
from typing import Any, Literal, override

from aiotractive.exceptions import TractiveError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_BUZZER, ATTR_LED, ATTR_LIVE_TRACKING, DOMAIN
from .coordinator import Trackables, TractiveConfigEntry, TractiveCoordinator
from .entity import TractiveEntity

_LOGGER = logging.getLogger(__name__)


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
    coordinator = entry.runtime_data.coordinator
    trackables = entry.runtime_data.trackables

    entities = [
        TractiveSwitch(coordinator, item, description)
        for description in SWITCH_TYPES
        for item in trackables
    ]

    async_add_entities(entities)


class TractiveSwitch(TractiveEntity, SwitchEntity):
    """Tractive switch."""

    entity_description: TractiveSwitchEntityDescription

    def __init__(
        self,
        coordinator: TractiveCoordinator,
        item: Trackables,
        description: TractiveSwitchEntityDescription,
    ) -> None:
        """Initialize switch entity."""
        super().__init__(
            coordinator,
            item.trackable,
            item.tracker_details,
        )
        self._attr_unique_id = f"{item.trackable['_id']}_{description.key}"
        self._tracker = item.tracker
        self._method = getattr(self, description.method)
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        status = self._tracker_status
        if status.power_saving_zone:
            return False
        return (
            super().available
            and getattr(status, self.entity_description.key) is not None
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = getattr(self._tracker_status, self.entity_description.key)
        super()._handle_coordinator_update()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on a switch."""
        try:
            result = await self._method(True)
        except TractiveError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_turn_on",
                translation_placeholders={"entity": self.entity_id},
            ) from error
        if result["pending"]:
            self._attr_is_on = True
            self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off a switch."""
        try:
            result = await self._method(False)
        except TractiveError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_turn_off",
                translation_placeholders={"entity": self.entity_id},
            ) from error
        if result["pending"]:
            self._attr_is_on = False
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
