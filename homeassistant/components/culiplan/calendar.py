"""Calendar entity for the Culiplan meal plan."""

from datetime import UTC, datetime, timedelta
import json
import logging
from typing import Any, cast

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CuliplanConfigEntry
from .coordinator import CuliplanCoordinator
from .helpers import build_device_info, parse_dt

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CuliplanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Culiplan calendar entities — one per meal plan."""
    coordinator = entry.runtime_data.coordinator
    meal_plans = (coordinator.data or {}).get("meal_plans", [])
    async_add_entities(
        CuliplanCalendar(coordinator, plan, entry) for plan in meal_plans
    )


class CuliplanCalendar(CoordinatorEntity[CuliplanCoordinator], CalendarEntity):
    """Calendar entity for a single Culiplan meal plan."""

    _attr_has_entity_name = True
    _attr_translation_key = "meal_plan"

    def __init__(
        self,
        coordinator: CuliplanCoordinator,
        plan: dict[str, Any],
        entry: CuliplanConfigEntry,
    ) -> None:
        """Bind the entity to a specific plan id within one config entry."""
        super().__init__(coordinator)
        self._plan_id: str = plan["id"]
        self._attr_unique_id = f"{entry.entry_id}_calendar_{self._plan_id}"
        self._attr_device_info = build_device_info(entry)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current / next upcoming event."""
        now = datetime.now(tz=UTC)
        upcoming = [e for e in self._build_events() if e.end > now]
        return upcoming[0] if upcoming else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose recipe IDs for the current / next event (no PII)."""
        ev = self.event
        if ev is None or ev.description is None:
            return {}
        try:
            return cast(dict[str, Any], json.loads(ev.description))
        except (ValueError, TypeError):
            return {}

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events within ``[start_date, end_date)``."""
        return [
            e for e in self._build_events() if e.start < end_date and e.end > start_date
        ]

    def _build_events(self) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        for plan in (self.coordinator.data or {}).get("meal_plans", []):
            if plan["id"] != self._plan_id:
                continue
            for slot in plan.get("slots", []):
                try:
                    start = parse_dt(slot["date"])
                    end = start + timedelta(hours=1)
                    description = json.dumps(
                        {
                            "recipe_id": slot.get("recipeId"),
                            "servings": slot.get("servings"),
                            "course": slot.get("course"),
                        }
                    )
                    events.append(
                        CalendarEvent(
                            start=start,
                            end=end,
                            summary=slot.get("title", "Meal"),
                            description=description,
                            uid=slot.get("id"),
                        )
                    )
                except (KeyError, ValueError) as err:
                    _LOGGER.debug("Skipping malformed meal slot: %s", err)
        return sorted(events, key=lambda e: e.start)
