"""DataUpdateCoordinator for the Bring! integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from bring_api import (
    Bring,
    BringAuthException,
    BringParseException,
    BringRequestException,
)
from bring_api.types import BringItemsResponse, BringList, BringUserSettingsResponse
from mashumaro.mixins.orjson import DataClassORJSONMixin

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BringData(DataClassORJSONMixin):
    """Coordinator data class."""

    lst: BringList
    content: BringItemsResponse


class BringDataUpdateCoordinator(DataUpdateCoordinator[dict[str, BringData]]):
    """A Bring Data Update Coordinator."""

    config_entry: ConfigEntry
    user_settings: BringUserSettingsResponse
    lists: list[BringList]

    def __init__(self, hass: HomeAssistant, bring: Bring) -> None:
        """Initialize the Bring data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
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
            raise UpdateFailed("Unable to connect and retrieve data from bring") from e
        except BringParseException as e:
            raise UpdateFailed("Unable to parse response from bring") from e
        except BringAuthException:
            # try to recover by refreshing access token, otherwise
            # initiate reauth flow
            try:
                await self.bring.retrieve_new_access_token()
            except (BringRequestException, BringParseException) as exc:
                raise UpdateFailed("Refreshing authentication token failed") from exc
            except BringAuthException as exc:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_authentication_exception",
                    translation_placeholders={CONF_EMAIL: self.bring.mail},
                ) from exc
            return self.data

        if self.previous_lists - (
            current_lists := {lst.listUuid for lst in self.lists}
        ):
            self._purge_deleted_lists()
        self.previous_lists = current_lists

        list_dict: dict[str, BringData] = {}
        for lst in self.lists:
            if (ctx := set(self.async_contexts())) and lst.listUuid not in ctx:
                continue
            try:
                items = await self.bring.get_list(lst.listUuid)
            except BringRequestException as e:
                raise UpdateFailed(
                    "Unable to connect and retrieve data from bring"
                ) from e
            except BringParseException as e:
                raise UpdateFailed("Unable to parse response from bring") from e
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
