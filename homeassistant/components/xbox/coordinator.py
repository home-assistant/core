"""Coordinator for the xbox integration."""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import Self, override

from httpx2 import HTTPStatusError, RequestError, TimeoutException
from pythonxbox.api.client import XboxLiveClient
from pythonxbox.api.provider.achievements.models import Achievement, Achievement360
from pythonxbox.api.provider.catalog.const import SYSTEM_PFN_ID_MAP
from pythonxbox.api.provider.catalog.models import AlternateIdType, Product
from pythonxbox.api.provider.people.models import Person
from pythonxbox.api.provider.smartglass.models import (
    SmartglassConsole,
    SmartglassConsoleStatus,
)
from pythonxbox.api.provider.titlehub.models import Title
from pythonxbox.common.exceptions import RateLimitExceededException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SWEEP_INTERVAL = timedelta(minutes=15)

type XboxConfigEntry = ConfigEntry[XboxCoordinators]


@dataclass
class ConsoleData:
    """Xbox console status data."""

    status: SmartglassConsoleStatus
    app_details: Product | None


@dataclass
class XboxData:
    """Xbox dataclass for presence update coordinator."""

    presence: dict[str, Person] = field(default_factory=dict)
    title_info: dict[str, Title] = field(default_factory=dict)
    achievement_totals: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class AchievementUnlock:
    """An unlocked achievement of an Xbox One or Xbox 360 title."""

    name: str
    description: str
    gamerscore: int
    game: str | None
    title_id: int
    rarity: str | None
    rarity_percentage: float | None
    time_unlocked: datetime
    image: str | None

    @classmethod
    def from_xboxone(cls, achievement: Achievement) -> Self:
        """Create from an Xbox One achievement."""
        return cls(
            name=achievement.name,
            description=achievement.description,
            gamerscore=next(
                (
                    int(reward.value)
                    for reward in achievement.rewards
                    if reward.type == "Gamerscore"
                ),
                0,
            ),
            game=achievement.title_associations[0].name,
            title_id=achievement.title_associations[0].id,
            rarity=(
                achievement.rarity.current_category.lower()
                if achievement.rarity
                else None
            ),
            rarity_percentage=(
                achievement.rarity.current_percentage if achievement.rarity else None
            ),
            time_unlocked=achievement.progression.time_unlocked,
            image=next(
                (
                    asset.url
                    for asset in achievement.media_assets
                    if asset.type == "Icon"
                ),
                None,
            ),
        )

    @classmethod
    def from_xbox360(cls, achievement: Achievement360) -> Self:
        """Create from an Xbox 360 achievement."""
        return cls(
            name=achievement.name,
            description=achievement.description,
            gamerscore=achievement.gamerscore,
            # Xbox 360 achievements carry neither, they are looked up when needed
            game=None,
            title_id=achievement.title_id,
            rarity=(
                achievement.rarity.current_category.lower()
                if achievement.rarity
                else None
            ),
            rarity_percentage=(
                achievement.rarity.current_percentage if achievement.rarity else None
            ),
            time_unlocked=achievement.time_unlocked,
            image=None,
        )


@dataclass
class XboxCoordinators:
    """Xbox coordinators."""

    consoles: XboxConsolesCoordinator
    status: XboxConsoleStatusCoordinator
    presence: XboxPresenceCoordinator
    achievements: XboxAchievementsCoordinator


class XboxBaseCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base coordinator for Xbox."""

    config_entry: XboxConfigEntry
    _update_inverval: timedelta

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: XboxConfigEntry,
        client: XboxLiveClient,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=self._update_interval,
        )
        self.client = client

    @abstractmethod
    async def update_data(self) -> _DataT:
        """Update coordinator data."""

    @override
    async def _async_update_data(self) -> _DataT:
        """Fetch console data."""

        try:
            return await self.update_data()
        except TimeoutException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            _LOGGER.debug("Xbox exception:", exc_info=True)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e


class XboxConsolesCoordinator(XboxBaseCoordinator[dict[str, SmartglassConsole]]):
    """Update list of Xbox consoles."""

    config_entry: XboxConfigEntry
    _update_interval = timedelta(minutes=10)

    @override
    async def update_data(self) -> dict[str, SmartglassConsole]:
        """Fetch console data."""

        consoles = await self.client.smartglass.get_console_list()

        _LOGGER.debug(
            "Found %d consoles: %s", len(consoles.result), consoles.model_dump()
        )

        return {console.id: console for console in consoles.result}


class XboxConsoleStatusCoordinator(XboxBaseCoordinator[dict[str, ConsoleData]]):
    """Update Xbox console Status."""

    config_entry: XboxConfigEntry
    _update_interval = timedelta(seconds=10)

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: XboxConfigEntry,
        client: XboxLiveClient,
        consoles: dict[str, SmartglassConsole],
    ) -> None:
        """Initialize."""
        super().__init__(hass, config_entry, client)
        self.data: dict[str, ConsoleData] = {}

        self.consoles: dict[str, SmartglassConsole] | None = consoles

    @override
    async def update_data(self) -> dict[str, ConsoleData]:
        """Fetch console data."""

        consoles: list[SmartglassConsole] = list(self.async_contexts())

        if not consoles and self.consoles is not None:
            consoles = list(self.consoles.values())
            self.consoles = None

        data: dict[str, ConsoleData] = {}
        for console in consoles:
            status = await self.client.smartglass.get_console_status(console.id)
            _LOGGER.debug("%s status: %s", console.name, status.model_dump())

            # Setup focus app
            app_details = (
                current_state.app_details
                if (current_state := self.data.get(console.id)) is not None
                and status.focus_app_aumid
                else None
            )

            if status.focus_app_aumid and (
                not current_state
                or status.focus_app_aumid != current_state.status.focus_app_aumid
            ):
                catalog_result = (
                    await self.client.catalog.get_product_from_alternate_id(
                        *self._resolve_app_id(status.focus_app_aumid)
                    )
                )

                if catalog_result.products:
                    app_details = catalog_result.products[0]

            data[console.id] = ConsoleData(status=status, app_details=app_details)

        return data

    def _resolve_app_id(self, focus_app_aumid: str) -> tuple[str, AlternateIdType]:
        app_id = focus_app_aumid.split("!", maxsplit=1)[0]
        id_type = AlternateIdType.PACKAGE_FAMILY_NAME

        if app_id in SYSTEM_PFN_ID_MAP:
            id_type = AlternateIdType.LEGACY_XBOX_PRODUCT_ID
            app_id = SYSTEM_PFN_ID_MAP[app_id][id_type]

        return app_id, id_type


class XboxPresenceCoordinator(XboxBaseCoordinator[XboxData]):
    """Update list of Xbox consoles."""

    config_entry: XboxConfigEntry
    _update_interval = timedelta(seconds=30)

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: XboxConfigEntry,
        client: XboxLiveClient,
    ) -> None:
        """Initialize."""
        super().__init__(hass, config_entry, client)

        self.title_data: dict[str, Title] = {}
        self.achievement_totals: dict[str, int] = {}

    @override
    async def update_data(self) -> XboxData:
        """Fetch presence data."""

        me = await self.client.people.get_friend_by_xuid(self.client.xuid)
        friends = await self.client.people.get_friends_own()

        presence_data = {self.client.xuid: me.people[0]}
        presence_data.update(
            {
                friend.xuid: friend
                for friend in friends.people
                if friend.xuid in self.friend_subentries()
            }
        )

        # retrieve title details
        for person in presence_data.values():
            if presence_detail := next(
                (
                    d
                    for d in person.presence_details or []
                    if d.state == "Active" and d.title_id and d.is_game and d.is_primary
                ),
                None,
            ):
                if (
                    person.xuid in self.title_data
                    and presence_detail.title_id
                    == self.title_data[person.xuid].title_id
                ):
                    # Nothing below runs again for an unchanged title, so a
                    # previously failed achievement lookup is retried here.
                    await self.update_achievement_total(
                        person.xuid,
                        presence_detail.title_id,
                        self.title_data[person.xuid],
                    )
                    continue
                try:
                    title = await self.client.titlehub.get_title_info_by_xuid(
                        person.xuid, presence_detail.title_id
                    )
                except HTTPStatusError as e:
                    if e.response.status_code == HTTPStatus.NOT_FOUND:
                        continue
                    raise
                self.title_data[person.xuid] = title.titles[0]
                self.achievement_totals.pop(person.xuid, None)
                await self.update_achievement_total(
                    person.xuid, presence_detail.title_id, title.titles[0]
                )
            else:
                self.title_data.pop(person.xuid, None)
                self.achievement_totals.pop(person.xuid, None)
            person.last_seen_date_time_utc = self.last_seen_timestamp(person)
        return XboxData(presence_data, self.title_data, self.achievement_totals)

    async def update_achievement_total(
        self, xuid: str, title_id: str, title: Title
    ) -> None:
        """Retrieve the real achievement total for a title."""

        # Titlehub reports a total of 0 for Xbox One titles as soon as a single
        # achievement has been unlocked, which renders the sensor attribute as
        # "57 / 0". The achievements API still knows the real total. Xbox 360
        # titles are unaffected and are skipped by this check.
        if (
            xuid in self.achievement_totals
            or title.achievement is None
            or title.achievement.total_achievements
        ):
            return

        try:
            progress = (
                await self.client.achievements.get_achievements_xboxone_gameprogress(
                    xuid, title_id
                )
            )
        except (HTTPStatusError, RateLimitExceededException, RequestError) as e:
            # Leave the total unset so the next update tries again.
            _LOGGER.debug(
                "Unable to retrieve achievement total for %s: %s", title_id, e
            )
            return

        # A zero is recorded as well, to stop the retry above.
        self.achievement_totals[xuid] = progress.paging_info.total_records

    def last_seen_timestamp(self, person: Person) -> datetime | None:
        """Returns the most recent of two timestamps."""

        # The Xbox API constantly fluctuates the "last seen"
        # timestamp between two close values, causing
        # unnecessary updates. We only accept the most
        # recent one as valid to prevent this.

        prev_dt = (
            prev_data.last_seen_date_time_utc
            if self.data and (prev_data := self.data.presence.get(person.xuid))
            else None
        )
        cur_dt = person.last_seen_date_time_utc

        if prev_dt and cur_dt:
            return max(prev_dt, cur_dt)

        return cur_dt

    def friend_subentries(self) -> set[str]:
        """Get configured friend subentries."""
        return {
            friend.unique_id
            for friend in self.config_entry.subentries.values()
            if friend.unique_id
        }


class XboxAchievementsCoordinator(
    DataUpdateCoordinator[dict[str, list[AchievementUnlock]]]
):
    """Update recently unlocked achievements."""

    config_entry: XboxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: XboxConfigEntry,
        client: XboxLiveClient,
        presence: XboxPresenceCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, config_entry=config_entry, name=DOMAIN)
        self.client = client
        self.presence = presence
        self.data = {}

        self.online: set[str] = set()
        self.last_sweep: datetime | None = None
        self.titles_360: dict[int, Title | None] = {}

    @override
    async def _async_update_data(self) -> dict[str, list[AchievementUnlock]]:
        """Fetch recently unlocked achievements."""

        online = {
            xuid
            for xuid, person in self.presence.data.presence.items()
            if person.presence_state == "Online"
        }
        # Anyone who just went offline is polled once more, to catch the
        # unlocks of their last minutes.
        xuids = online | self.online
        self.online = online

        # People who appear offline look offline to presence too, so everyone
        # is polled now and then.
        now = dt_util.utcnow()
        if self.last_sweep is None or now - self.last_sweep >= SWEEP_INTERVAL:
            xuids = set(self.presence.data.presence)
            self.last_sweep = now

        achievements = self.client.achievements
        data: dict[str, list[AchievementUnlock]] = {}
        for xuid in xuids:
            try:
                xboxone = await achievements.get_achievements_xboxone_recent_unlocks(
                    xuid
                )
                xbox360 = await achievements.get_achievements_xbox360_recent_unlocks(
                    xuid
                )
            except (HTTPStatusError, RateLimitExceededException, RequestError) as e:
                _LOGGER.debug("Unable to retrieve achievements for %s: %s", xuid, e)
                continue

            # Achievements without a known unlock time carry a placeholder date.
            data[xuid] = [
                *(
                    AchievementUnlock.from_xboxone(achievement)
                    for achievement in xboxone.achievements
                    if achievement.progress_state == "Achieved"
                    and achievement.progression.time_unlocked.year > 1
                ),
                *(
                    AchievementUnlock.from_xbox360(achievement)
                    for achievement in xbox360.achievements
                    if achievement.unlocked and achievement.time_unlocked.year > 1753
                ),
            ]

        if xuids and not data:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            )
        return data

    async def async_get_360_title(self, title_id: int) -> Title | None:
        """Return the title details of an Xbox 360 game."""

        if title_id not in self.titles_360:
            try:
                response = await self.client.titlehub.get_title_info(str(title_id))
            except HTTPStatusError as e:
                _LOGGER.debug("Unable to retrieve title %s: %s", title_id, e)
                if e.response.status_code != HTTPStatus.NOT_FOUND:
                    return None
                # Titlehub doesn't know every Xbox 360 game, so don't ask again.
                self.titles_360[title_id] = None
            except RequestError as e:
                _LOGGER.debug("Unable to retrieve title %s: %s", title_id, e)
                return None
            else:
                self.titles_360[title_id] = next(iter(response.titles), None)

        return self.titles_360[title_id]
