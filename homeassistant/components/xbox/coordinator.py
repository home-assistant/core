"""Coordinator for the xbox integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from http import HTTPStatus
import logging

from httpx import HTTPStatusError, RequestError, TimeoutException
from pythonxbox.api.client import XboxLiveClient
from pythonxbox.api.provider.catalog.const import SYSTEM_PFN_ID_MAP
from pythonxbox.api.provider.catalog.models import AlternateIdType, Product
from pythonxbox.api.provider.people.models import Person
from pythonxbox.api.provider.smartglass.models import (
    SmartglassConsoleList,
    SmartglassConsoleStatus,
)
from pythonxbox.api.provider.titlehub.models import Title

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import api
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
    """Xbox dataclass for update coordinator."""

    consoles: dict[str, ConsoleData] = field(default_factory=dict)
    presence: dict[str, Person] = field(default_factory=dict)
    title_info: dict[str, Title] = field(default_factory=dict)


@dataclass
class XboxCoordinators:
    """Xbox coordinators."""

    status: XboxUpdateCoordinator
    consoles: XboxConsolesCoordinator


class XboxUpdateCoordinator(DataUpdateCoordinator[XboxData]):
    """Store Xbox Console Status."""

    config_entry: XboxConfigEntry
    consoles: SmartglassConsoleList
    client: XboxLiveClient

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: XboxConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
        )
        self.data = XboxData()
        self.current_friends: set[str] = set()
        self.title_data: dict[str, Title] = {}

    async def _async_setup(self) -> None:
        """Set up coordinator."""
        try:
            implementation = await async_get_config_entry_implementation(
                self.hass, self.config_entry
            )
        except ImplementationUnavailableError as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="oauth2_implementation_unavailable",
            ) from e

        session = OAuth2Session(self.hass, self.config_entry, implementation)
        async_session = get_async_client(self.hass)
        auth = api.AsyncConfigEntryAuth(async_session, session)
        self.client = XboxLiveClient(auth)

        try:
            self.consoles = await self.client.smartglass.get_console_list()
        except TimeoutException as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            _LOGGER.debug("Xbox exception:", exc_info=True)
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e

        _LOGGER.debug(
            "Found %d consoles: %s",
            len(self.consoles.result),
            self.consoles.model_dump(),
        )

    async def _async_update_data(self) -> XboxData:
        """Fetch the latest console status."""
        # Update Console Status
        new_console_data: dict[str, ConsoleData] = {}
        for console in self.consoles.result:
            current_state = self.data.consoles.get(console.id)
            try:
                status = await self.client.smartglass.get_console_status(console.id)
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
            _LOGGER.debug(
                "%s status: %s",
                console.name,
                status.model_dump(),
            )

            # Setup focus app
            app_details: Product | None = None
            if current_state is not None:
                app_details = current_state.app_details

            if status.focus_app_aumid:
                if (
                    not current_state
                    or status.focus_app_aumid != current_state.status.focus_app_aumid
                ):
                    app_id = status.focus_app_aumid.split("!")[0]
                    id_type = AlternateIdType.PACKAGE_FAMILY_NAME
                    if app_id in SYSTEM_PFN_ID_MAP:
                        id_type = AlternateIdType.LEGACY_XBOX_PRODUCT_ID
                        app_id = SYSTEM_PFN_ID_MAP[app_id][id_type]
                    try:
                        catalog_result = (
                            await self.client.catalog.get_product_from_alternate_id(
                                app_id, id_type
                            )
                        )
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
                    else:
                        if catalog_result.products:
                            app_details = catalog_result.products[0]
            else:
                app_details = None

            new_console_data[console.id] = ConsoleData(
                status=status, app_details=app_details
            )

        # Update user presence
        try:
            batch = await self.client.people.get_friends_by_xuid(self.client.xuid)
            friends = await self.client.people.get_friends_own()
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
        else:
            presence_data = {self.client.xuid: batch.people[0]}
            presence_data.update({friend.xuid: friend for friend in friends.people})

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
                except TimeoutException as e:
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="timeout_exception",
                    ) from e
                except HTTPStatusError as e:
                    _LOGGER.debug("Xbox exception:", exc_info=True)
                    if e.response.status_code == HTTPStatus.NOT_FOUND:
                        continue
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="request_exception",
                    ) from e
                except RequestError as e:
                    _LOGGER.debug("Xbox exception:", exc_info=True)
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="request_exception",
                    ) from e
                self.title_data[person.xuid] = title.titles[0]
            else:
                self.title_data.pop(person.xuid, None)
            person.last_seen_date_time_utc = self.last_seen_timestamp(person)
        return XboxData(new_console_data, presence_data, self.title_data)

    def last_seen_timestamp(self, person: Person) -> datetime | None:
        """Returns the most recent of two timestamps."""

        # The Xbox API constantly fluctuates the "last seen" timestamp between two close values,
        # causing unnecessary updates. We only accept the most recent one as valild to prevent this.
        if not (prev_data := self.data.presence.get(person.xuid)):
            return person.last_seen_date_time_utc

        prev_dt = prev_data.last_seen_date_time_utc
        cur_dt = person.last_seen_date_time_utc

        if prev_dt and cur_dt:
            return max(prev_dt, cur_dt)

        return cur_dt

    def configured_as_entry(self) -> set[str]:
        """Get xuids of configured entries."""

        return {
            entry.unique_id
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.unique_id is not None
        }


class XboxConsolesCoordinator(DataUpdateCoordinator[SmartglassConsoleList]):
    """Update list of Xbox consoles."""

    config_entry: XboxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: XboxConfigEntry,
        coordinator: XboxUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=10),
        )
        self.client = coordinator.client
        self.async_set_updated_data(coordinator.consoles)

    async def _async_update_data(self) -> SmartglassConsoleList:
        """Fetch console data."""

        try:
            return await self.client.smartglass.get_console_list()
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
