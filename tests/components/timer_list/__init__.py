"""Tests for the Timer list integration."""

from datetime import timedelta

from homeassistant.components.timer_list import DOMAIN, TimerItem, TimerListEntity
from homeassistant.components.timer_list.const import (
    TimerListEntityFeature,
    TimerListEventType,
    TimerStatus,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util, ulid as ulid_util

from tests.common import MockConfigEntry, MockPlatform, mock_platform

TEST_DOMAIN = "test"

_ARCHIVE_EVENTS = {
    TimerStatus.FINISHED: TimerListEventType.FINISHED,
    TimerStatus.CANCELLED: TimerListEventType.CANCELLED,
}


class MockFlow(ConfigFlow):
    """Test flow."""


class MockTimerListEntity(TimerListEntity):
    """A minimal timer list, standing in for a real provider.

    Implements just enough of the entity contract to drive the platform's
    services, websocket API and triggers. It deliberately does not schedule
    anything: where timers are stored and when they elapse belongs to a
    concrete implementation, so these tests stay about the base platform.
    """

    _attr_supported_features = (
        TimerListEntityFeature.CREATE_TIMER
        | TimerListEntityFeature.PAUSE_TIMER
        | TimerListEntityFeature.CANCEL_TIMER
        | TimerListEntityFeature.FINISH_TIMER
        | TimerListEntityFeature.ADD_TIME
        | TimerListEntityFeature.REMOVE_TIMER
    )

    def __init__(self, name: str = "Timers") -> None:
        """Initialize entity."""
        super().__init__()
        self._attr_name = name
        self._attr_unique_id = ulid_util.ulid_now()
        self._timers: dict[str, TimerItem] = {}

    @property
    def timers(self) -> list[TimerItem]:
        """Return the timers in the list."""
        return list(self._timers.values())

    def _get_timer(self, timer_id: str) -> TimerItem:
        """Return a timer by id or raise if it does not exist."""
        if (timer := self._timers.get(timer_id)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="timer_not_found",
                translation_placeholders={"timer_id": timer_id},
            )
        return timer

    async def async_create_timer(self, *, name: str | None, duration: timedelta) -> str:
        """Create a new timer, returning its id."""
        now = dt_util.utcnow()
        timer = TimerItem(
            timer_id=ulid_util.ulid_now(),
            name=name,
            status=TimerStatus.ACTIVE,
            created_duration=duration,
            created_at=now,
            finishes_at=now + duration,
        )
        self._timers[timer.timer_id] = timer
        self._notify(TimerListEventType.CREATED, timer)
        return timer.timer_id

    async def async_pause_timer(self, timer_id: str) -> None:
        """Pause an active timer."""
        timer = self._get_timer(timer_id)
        timer.paused_remaining = timer.remaining_at(dt_util.utcnow())
        timer.finishes_at = None
        timer.status = TimerStatus.PAUSED
        self._notify(TimerListEventType.PAUSED, timer)

    async def async_unpause_timer(self, timer_id: str) -> None:
        """Resume a paused timer."""
        timer = self._get_timer(timer_id)
        timer.finishes_at = dt_util.utcnow() + (timer.paused_remaining or timedelta(0))
        timer.paused_remaining = None
        timer.status = TimerStatus.ACTIVE
        self._notify(TimerListEventType.UNPAUSED, timer)

    async def async_cancel_timer(self, timer_id: str) -> None:
        """Cancel a timer, archiving it in the ``cancelled`` state."""
        self._archive(self._get_timer(timer_id), TimerStatus.CANCELLED)

    async def async_finish_timer(self, timer_id: str) -> None:
        """Finish a timer, archiving it in the ``finished`` state."""
        self._archive(self._get_timer(timer_id), TimerStatus.FINISHED)

    async def async_add_time(self, timer_id: str, duration: timedelta) -> None:
        """Add (or, with a negative duration, subtract) time on a timer."""
        timer = self._get_timer(timer_id)
        now = dt_util.utcnow()
        timer.finishes_at = now + timer.remaining_at(now) + duration
        self._notify(TimerListEventType.TIME_CHANGED, timer, delta=duration)

    async def async_remove_timer(self, timer_id: str) -> None:
        """Remove a timer from the list regardless of its status."""
        timer = self._get_timer(timer_id)
        del self._timers[timer_id]
        self._notify(TimerListEventType.REMOVED, timer)

    def _archive(self, timer: TimerItem, status: TimerStatus) -> None:
        """Move a timer to a terminal status and notify subscribers."""
        timer.status = status
        timer.finishes_at = None
        timer.paused_remaining = None
        timer.ended_at = dt_util.utcnow()
        self._notify(_ARCHIVE_EVENTS[status], timer)


async def create_mock_platform(
    hass: HomeAssistant,
    entities: list[TimerListEntity],
) -> MockConfigEntry:
    """Create a timer_list platform with the specified entities."""

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test timer_list platform via config entry."""
        async_add_entities(entities)

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
