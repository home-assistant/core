"""The sensor entities for the ElevenLabs integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from logging import getLogger

from elevenlabs.types import UsageCharactersResponseModel
from propcache import cached_property

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ElevenLabsConfigEntry
from .coordinator import BREAKDOWN_KEY, ElevenLabsDataUpdateCoordinator

_LOGGER = getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ElevenLabsSensorEntityDescription(SensorEntityDescription):
    """Describes ElevenLabs sensor entity."""

    value_fn: Callable[[UsageCharactersResponseModel], int]


def characters_sum_from_timestamp(
    data: UsageCharactersResponseModel, timestamp: datetime
) -> int:
    """Return the sum of characters used since the given timestamp."""
    # ElevenLabs timestamps are 0:00 UTC, so we need to adjust the time to match
    timestamp = datetime(timestamp.year, timestamp.month, timestamp.day, tzinfo=UTC)
    now = datetime.now(UTC)
    curr = timestamp
    characters = 0
    while curr < now:
        curr_unix = int(curr.timestamp() * 1_000)
        curr_idx = data.time.index(curr_unix)
        _LOGGER.debug(
            "Day %s: %s characters",
            curr.strftime("%Y-%m-%d"),
            data.usage[BREAKDOWN_KEY][curr_idx],
        )
        characters += data.usage[BREAKDOWN_KEY][curr_idx]
        curr += timedelta(days=1)
    return characters


def characters_this_month(data: UsageCharactersResponseModel) -> int:
    """Return the number of characters used this month."""
    now = datetime.now(UTC)
    first_day = datetime(now.year, now.month, 1, tzinfo=UTC)
    return characters_sum_from_timestamp(data, first_day)


def characters_7_days(data: UsageCharactersResponseModel) -> int:
    """Return the number of characters used in the last 7 days."""
    now = datetime.now(UTC)
    last_seven = now - timedelta(days=6)  # Last 7 days, including today, so 6 days ago
    return characters_sum_from_timestamp(data, last_seven)


def characters_today(data: UsageCharactersResponseModel) -> int:
    """Return the number of characters used today."""
    now = datetime.now(UTC)
    # ElevenLabs timestamps are 0:00 UTC, so we need to adjust the current time to match
    today = datetime(now.year, now.month, now.day, tzinfo=UTC)
    today_unix = int(today.timestamp() * 1_000)
    today_idx = data.time.index(today_unix)
    return data.usage[BREAKDOWN_KEY][today_idx]


SENSORS: tuple[ElevenLabsSensorEntityDescription, ...] = (
    ElevenLabsSensorEntityDescription(
        key="total_characters",
        translation_key="total_characters",
        value_fn=lambda data: sum(data.usage[BREAKDOWN_KEY]),
    ),
    ElevenLabsSensorEntityDescription(
        key="characters_today",
        translation_key="characters_today",
        value_fn=characters_today,
    ),
    ElevenLabsSensorEntityDescription(
        key="characters_7_days",
        translation_key="characters_7_days",
        value_fn=characters_7_days,
    ),
    ElevenLabsSensorEntityDescription(
        key="characters_this_month",
        translation_key="characters_this_month",
        value_fn=characters_this_month,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElevenLabsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ElevenLabs sensors based on a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        ElevenLabsUsageEntity(
            coordinator=coordinator,
            description=description,
            entry_id=f"{entry.entry_id}",
        )
        for description in SENSORS
    )


class ElevenLabsUsageEntity(
    CoordinatorEntity[ElevenLabsDataUpdateCoordinator], SensorEntity
):
    """ElevenLabs usage entity for getting usage metrics."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        *,
        coordinator: ElevenLabsDataUpdateCoordinator,
        description: ElevenLabsSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the ElevenLabs usage entity."""
        super().__init__(coordinator)
        self.entity_description: ElevenLabsSensorEntityDescription = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        # Report the value from the description's value_fn
        return self.entity_description.value_fn(self.coordinator.data)
