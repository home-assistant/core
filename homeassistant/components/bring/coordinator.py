"""DataUpdateCoordinator for the Bring! integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from bring_api import (
    Bring,
    BringActivityResponse,
    BringAuthException,
    BringItemsResponse,
    BringList,
    BringParseException,
    BringRequestException,
    BringUserSettingsResponse,
    BringUsersResponse,
)
from mashumaro.mixins.orjson import DataClassORJSONMixin

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type BringConfigEntry = ConfigEntry[BringCoordinators]


@dataclass
class BringCoordinators:
    """Data class holding coordinators."""

    data: BringDataUpdateCoordinator
    activity: BringActivityCoordinator


@dataclass(frozen=True)
class BringData(DataClassORJSONMixin):
    """Coordinator data class."""

    lst: BringList
    content: BringItemsResponse


@dataclass(frozen=True)
class BringActivityData(DataClassORJSONMixin):
    """Coordinator data class."""

    activity: BringActivityResponse
    users: BringUsersResponse


class BringBaseCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Bring base coordinator."""

    config_entry: BringConfigEntry
    lists: list[BringList]


class BringDataUpdateCoordinator(BringBaseCoordinator[dict[str, BringData]]):
    """A Bring Data Update Coordinator."""

    user_settings: BringUserSettingsResponse

    def __init__(
        self, hass: HomeAssistant, config_entry: BringConfigEntry, bring: Bring
    ) -> None:
        """Initialize the Bring data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=90),
        )
        self.bring = bring
        self.previous_lists: set[str] = set()

    async def _async_update_data(self) -> dict[str, BringData]:
        """Fetch the latest data from bring."""

        try:
            self.lists = (await self.bring.load_lists()).lists
        except BringRequestException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="setup_request_exception",
            ) from e
        except BringParseException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="setup_parse_exception",
            ) from e
        except BringAuthException as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="setup_authentication_exception",
                translation_placeholders={CONF_EMAIL: self.bring.mail},
            ) from e

        if self.previous_lists - (
            current_lists := {lst.listUuid for lst in self.lists}
        ):
            self._purge_deleted_lists()
        new_lists = current_lists - self.previous_lists
        self.previous_lists = current_lists

        list_dict: dict[str, BringData] = {}
        for lst in self.lists:
            if (
                (ctx := set(self.async_contexts()))
                and lst.listUuid not in ctx
                and lst.listUuid not in new_lists
            ):
                continue
            try:
                items = await self.bring.get_list(lst.listUuid)
            except BringRequestException as e:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_request_exception",
                ) from e
            except BringParseException as e:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_parse_exception",
                ) from e
            else:
                list_dict[lst.listUuid] = BringData(lst, items)

        return list_dict

    async def _async_setup(self) -> None:
        """Set up coordinator."""

        try:
            await self.bring.login()
            self.user_settings = await self.bring.get_all_user_settings()
            self.lists = (await self.bring.load_lists()).lists
        except BringRequestException as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="setup_request_exception",
            ) from e
        except BringParseException as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="setup_parse_exception",
            ) from e
        except BringAuthException as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="setup_authentication_exception",
                translation_placeholders={CONF_EMAIL: self.bring.mail},
            ) from e
        self._purge_deleted_lists()

    def _purge_deleted_lists(self) -> None:
        """Purge device entries of deleted lists."""

        device_reg = dr.async_get(self.hass)
        identifiers = {
            (DOMAIN, f"{self.config_entry.unique_id}_{lst.listUuid}")
            for lst in self.lists
        }
        for device in dr.async_entries_for_config_entry(
            device_reg, self.config_entry.entry_id
        ):
            if not set(device.identifiers) & identifiers:
                _LOGGER.debug("Removing obsolete device entry %s", device.name)
                device_reg.async_update_device(
                    device.id, remove_config_entry_id=self.config_entry.entry_id
                )


class BringActivityCoordinator(BringBaseCoordinator[dict[str, BringActivityData]]):
    """A Bring Activity Data Update Coordinator."""

    user_settings: BringUserSettingsResponse

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BringConfigEntry,
        coordinator: BringDataUpdateCoordinator,
    ) -> None:
        """Initialize the Bring Activity data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=10),
        )

        self.coordinator = coordinator
        self.lists = coordinator.lists

    async def _async_update_data(self) -> dict[str, BringActivityData]:
        """Fetch activity data from bring."""

        list_dict: dict[str, BringActivityData] = {}
        for lst in self.lists:
            if (
                ctx := set(self.coordinator.async_contexts())
            ) and lst.listUuid not in ctx:
                continue
            try:
                activity = await self.coordinator.bring.get_activity(lst.listUuid)
                users = await self.coordinator.bring.get_list_users(lst.listUuid)
            except BringAuthException as e:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_authentication_exception",
                    translation_placeholders={CONF_EMAIL: self.coordinator.bring.mail},
                ) from e
            except BringRequestException as e:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_request_exception",
                ) from e
            except BringParseException as e:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_parse_exception",
                ) from e
            else:
                list_dict[lst.listUuid] = BringActivityData(activity, users)

        return list_dict
