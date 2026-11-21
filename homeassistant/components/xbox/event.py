"""Event platform for the Xbox integration."""

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, override

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import AchievementUnlock, XboxAchievementsCoordinator, XboxConfigEntry
from .entity import to_https

PARALLEL_UPDATES = 0

EVENT_ACHIEVEMENT_UNLOCKED = "achievement_unlocked"

# Unlocks older than this, e.g. after a long downtime, are not announced.
STALE_AFTER = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event platform."""
    coordinator = entry.runtime_data.achievements

    if TYPE_CHECKING:
        assert entry.unique_id
    async_add_entities([XboxAchievementEventEntity(coordinator, entry.unique_id)])

    for subentry_id, subentry in entry.subentries.items():
        if (
            subentry.unique_id
            and subentry.unique_id in coordinator.presence.data.presence
            and subentry.subentry_type == "friend"
        ):
            async_add_entities(
                [XboxAchievementEventEntity(coordinator, subentry.unique_id)],
                config_subentry_id=subentry_id,
            )


class XboxAchievementEventEntity(
    CoordinatorEntity[XboxAchievementsCoordinator], EventEntity
):
    """Event entity for unlocked achievements."""

    _attr_has_entity_name = True
    _attr_translation_key = EVENT_ACHIEVEMENT_UNLOCKED
    _attr_event_types = [EVENT_ACHIEVEMENT_UNLOCKED]
    _unrecorded_attributes = frozenset({"description", "image", "entity_picture"})

    def __init__(self, coordinator: XboxAchievementsCoordinator, xuid: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.xuid = xuid
        self.last_unlock: datetime | None = None
        self._trigger_lock = asyncio.Lock()

        self._attr_unique_id = f"{xuid}_{EVENT_ACHIEVEMENT_UNLOCKED}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, xuid)},
            manufacturer="Microsoft",
            model="Xbox Network",
            name=coordinator.presence.data.presence[xuid].gamertag,
        )

    @callback
    def _async_handle_event(self) -> None:
        """Handle newly unlocked achievements."""
        if (unlocks := self.coordinator.data.get(self.xuid)) is None:
            return

        # Without any unlocks yet, there's no history to hold back.
        latest = max(
            (unlock.time_unlocked for unlock in unlocks),
            default=datetime.min.replace(tzinfo=dt_util.UTC),
        )
        if self.last_unlock is None:
            # Nothing to compare against yet, so all of it is history.
            self.last_unlock = latest
            return

        stale = dt_util.utcnow() - STALE_AFTER
        new_unlocks = sorted(
            (
                unlock
                for unlock in unlocks
                if unlock.time_unlocked > self.last_unlock
                and unlock.time_unlocked > stale
            ),
            key=lambda unlock: unlock.time_unlocked,
        )
        self.last_unlock = max(self.last_unlock, latest)

        if new_unlocks:
            self.coordinator.config_entry.async_create_background_task(
                self.hass,
                self._async_trigger_unlocks(new_unlocks),
                f"{DOMAIN}_{self.xuid}_{EVENT_ACHIEVEMENT_UNLOCKED}",
            )

    async def _async_trigger_unlocks(self, unlocks: list[AchievementUnlock]) -> None:
        """Trigger an event for each unlock, oldest first."""
        # A batch still looking up its game holds back the next, to keep the order.
        async with self._trigger_lock:
            for unlock in unlocks:
                game, image = unlock.game, unlock.image
                if unlock.game is None and (
                    title := await self.coordinator.async_get_360_title(unlock.title_id)
                ):
                    game, image = title.name, title.display_image

                self._trigger_event(
                    EVENT_ACHIEVEMENT_UNLOCKED,
                    {
                        "name": unlock.name,
                        "description": unlock.description,
                        "gamerscore": unlock.gamerscore,
                        "game": game,
                        "title_id": unlock.title_id,
                        "rarity": unlock.rarity,
                        "rarity_percentage": unlock.rarity_percentage,
                        "time_unlocked": unlock.time_unlocked,
                        "image": to_https(image) if image else None,
                    },
                )
                self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the time of the last unlock."""
        await super().async_added_to_hass()
        if (
            event_data := await self.async_get_last_event_data()
        ) and event_data.last_event_attributes:
            time_unlocked = event_data.last_event_attributes["time_unlocked"]
            # It's only a string when restored from storage, not after a reload.
            self.last_unlock = (
                time_unlocked
                if isinstance(time_unlocked, datetime)
                else dt_util.parse_datetime(time_unlocked)
            )
        self._async_handle_event()

    @override
    def _handle_coordinator_update(self) -> None:
        self._async_handle_event()
        return super()._handle_coordinator_update()

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""

        return self.state_attributes.get("image") or super().entity_picture
