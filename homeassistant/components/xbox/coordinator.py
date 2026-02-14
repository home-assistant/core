"""Coordinator for the xbox integration."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import ClassVar

from httpx import HTTPStatusError, RequestError, TimeoutException
from pythonxbox.api.client import XboxLiveClient
from pythonxbox.api.provider.catalog.const import SYSTEM_PFN_ID_MAP
from pythonxbox.api.provider.catalog.models import AlternateIdType, Product
from pythonxbox.api.provider.people.models import Person
from pythonxbox.api.provider.smartglass.models import (
    SmartglassConsole,
    SmartglassConsoleStatus,
)
from pythonxbox.api.provider.titlehub.models import Title

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

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


@dataclass
class XboxCoordinators:
    """Xbox coordinators."""

    consoles: XboxConsolesCoordinator
    status: XboxConsoleStatusCoordinator
    presence: XboxPresenceCoordinator


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

    async def update_data(self) -> dict[str, SmartglassConsole]:
        """Fetch console data."""

        consoles = await self.client.smartglass.get_console_list()

        _LOGGER.debug(
            "Found %d consoles: %s", len(consoles.result), consoles.model_dump()
        )

        device_reg = dr.async_get(self.hass)
        identifiers = {(DOMAIN, console.id) for console in consoles.result}
        for device in dr.async_entries_for_config_entry(
            device_reg, self.config_entry.entry_id
        ):
            if (
                device.entry_type is not DeviceEntryType.SERVICE
                and not set(device.identifiers) & identifiers
            ):
                _LOGGER.debug("Removing stale device %s", device.name)
                device_reg.async_update_device(
                    device.id, remove_config_entry_id=self.config_entry.entry_id
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
    title_data: ClassVar[dict[str, Title]] = {}

    async def update_data(self) -> XboxData:
        """Fetch presence data."""

        batch = await self.client.people.get_friends_by_xuid(self.client.xuid)
        friends = await self.client.people.get_friends_own()

        presence_data = {self.client.xuid: batch.people[0]}
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
                    continue
                try:
                    title = await self.client.titlehub.get_title_info(
                        presence_detail.title_id
                    )
                except HTTPStatusError as e:
                    if e.response.status_code == HTTPStatus.NOT_FOUND:
                        continue
                    raise
                self.title_data[person.xuid] = title.titles[0]
            else:
                self.title_data.pop(person.xuid, None)
            person.last_seen_date_time_utc = self.last_seen_timestamp(person)
        return XboxData(presence_data, self.title_data)

    def last_seen_timestamp(self, person: Person) -> datetime | None:
        """Returns the most recent of two timestamps."""

        # The Xbox API constantly fluctuates the "last seen" timestamp between two close values,
        # causing unnecessary updates. We only accept the most recent one as valild to prevent this.

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
