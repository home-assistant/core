"""Coordinator for the xbox integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging

from httpx import HTTPStatusError, RequestError, TimeoutException
from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.catalog.const import SYSTEM_PFN_ID_MAP
from xbox.webapi.api.provider.catalog.models import AlternateIdType, Product
from xbox.webapi.api.provider.people.models import Person
from xbox.webapi.api.provider.smartglass.models import (
    SmartglassConsoleList,
    SmartglassConsoleStatus,
)
from xbox.webapi.common.signed_session import SignedSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import api
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type XboxConfigEntry = ConfigEntry[XboxUpdateCoordinator]


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


class XboxUpdateCoordinator(DataUpdateCoordinator[XboxData]):
    """Store Xbox Console Status."""

    config_entry: ConfigEntry
    consoles: SmartglassConsoleList
    client: XboxLiveClient

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.data = XboxData()
        self.current_friends: set[str] = set()

    async def _async_setup(self) -> None:
        """Set up coordinator."""
        try:
            implementation = (
                await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    self.hass, self.config_entry
                )
            )
        except ValueError as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="request_exception",
                translation_placeholders={"error": str(e)},
            ) from e

        session = config_entry_oauth2_flow.OAuth2Session(
            self.hass, self.config_entry, implementation
        )
        signed_session = await self.hass.async_add_executor_job(SignedSession)
        auth = api.AsyncConfigEntryAuth(signed_session, session)
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
                translation_placeholders={"error": str(e)},
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
                            translation_placeholders={"error": str(e)},
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
            batch = await self.client.people.get_friends_own_batch([self.client.xuid])
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
                translation_placeholders={"error": str(e)},
            ) from e
        else:
            presence_data = {self.client.xuid: batch.people[0]}
            presence_data.update(
                {friend.xuid: friend for friend in friends.people if friend.is_favorite}
            )

        if (
            self.current_friends
            - (new_friends := {x.xuid for x in presence_data.values()})
            or not self.current_friends
        ):
            self.remove_stale_devices(presence_data)
        self.current_friends = new_friends

        return XboxData(new_console_data, presence_data)

    def remove_stale_devices(self, presence_data: dict[str, Person]) -> None:
        """Remove stale devices from registry."""

        device_reg = dr.async_get(self.hass)
        identifiers = {(DOMAIN, xuid) for xuid in set(presence_data)} | {
            (DOMAIN, console.id) for console in self.consoles.result
        }

        for device in dr.async_entries_for_config_entry(
            device_reg, self.config_entry.entry_id
        ):
            if not set(device.identifiers) & identifiers:
                _LOGGER.debug("Removing stale device %s", device.name)
                device_reg.async_update_device(
                    device.id, remove_config_entry_id=self.config_entry.entry_id
                )
