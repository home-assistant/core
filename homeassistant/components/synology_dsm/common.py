"""The Synology DSM component."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
import logging

from awesomeversion import AwesomeVersion
from synology_dsm import SynologyDSM
from synology_dsm.api.core.security import SynoCoreSecurity
from synology_dsm.api.core.system import SynoCoreSystem
from synology_dsm.api.core.upgrade import SynoCoreUpgrade
from synology_dsm.api.core.utilization import SynoCoreUtilization
from synology_dsm.api.dsm.information import SynoDSMInformation
from synology_dsm.api.dsm.network import SynoDSMNetwork
from synology_dsm.api.file_station import SynoFileStation
from synology_dsm.api.photos import SynoPhotos
from synology_dsm.api.storage.storage import SynoStorage
from synology_dsm.api.surveillance_station import SynoSurveillanceStation
from synology_dsm.exceptions import (
    SynologyDSMAPIErrorException,
    SynologyDSMException,
    SynologyDSMRequestException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BACKUP_PATH,
    CONF_DEVICE_TOKEN,
    DEFAULT_TIMEOUT,
    DOMAIN,
    EXCEPTION_DETAILS,
    EXCEPTION_UNKNOWN,
    ISSUE_MISSING_BACKUP_SETUP,
    SYNOLOGY_CONNECTION_EXCEPTIONS,
)

LOGGER = logging.getLogger(__name__)


class SynoApi:
    """Class to interface with Synology DSM API."""

    dsm: SynologyDSM

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the API wrapper class."""
        self._hass = hass
        self._entry = entry
        if entry.data.get(CONF_SSL):
            self.config_url = f"https://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
        else:
            self.config_url = f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"

        # DSM APIs
        self.file_station: SynoFileStation | None = None
        self.information: SynoDSMInformation | None = None
        self.network: SynoDSMNetwork | None = None
        self.photos: SynoPhotos | None = None
        self.security: SynoCoreSecurity | None = None
        self.storage: SynoStorage | None = None
        self.surveillance_station: SynoSurveillanceStation | None = None
        self.system: SynoCoreSystem | None = None
        self.upgrade: SynoCoreUpgrade | None = None
        self.utilisation: SynoCoreUtilization | None = None

        # Should we fetch them
        self._fetching_entities: dict[str, set[str]] = {}
        self._with_file_station = True
        self._with_information = True
        self._with_photos = True
        self._with_security = True
        self._with_storage = True
        self._with_surveillance_station = True
        self._with_system = True
        self._with_upgrade = True
        self._with_utilisation = True

        self._login_future: asyncio.Future[None] | None = None

    async def async_login(self) -> None:
        """Login to the Synology DSM API.

        This function will only login once if called multiple times
        by multiple different callers.

        If a login is already in progress, the function will await the
        login to complete before returning.
        """
        if self._login_future:
            return await self._login_future

        self._login_future = self._hass.loop.create_future()
        try:
            await self.dsm.login()
            self._login_future.set_result(None)
        except BaseException as err:
            if not self._login_future.done():
                self._login_future.set_exception(err)
            with suppress(BaseException):
                # Clear the flag as its normal that nothing
                # will wait for this future to be resolved
                # if there are no concurrent login attempts
                await self._login_future
            raise
        finally:
            self._login_future = None

    async def async_setup(self) -> None:
        """Start interacting with the NAS."""
        session = async_get_clientsession(self._hass, self._entry.data[CONF_VERIFY_SSL])
        self.dsm = SynologyDSM(
            session,
            self._entry.data[CONF_HOST],
            self._entry.data[CONF_PORT],
            self._entry.data[CONF_USERNAME],
            self._entry.data[CONF_PASSWORD],
            self._entry.data[CONF_SSL],
            timeout=DEFAULT_TIMEOUT,
            device_token=self._entry.data.get(CONF_DEVICE_TOKEN),
        )
        await self.async_login()

        self.information = self.dsm.information
        await self.information.update()

        # check if surveillance station is used
        self._with_surveillance_station = bool(
            self.dsm.apis.get(SynoSurveillanceStation.CAMERA_API_KEY)
        )
        if self._with_surveillance_station:
            try:
                await self.dsm.surveillance_station.update()
            except SYNOLOGY_CONNECTION_EXCEPTIONS:
                self._with_surveillance_station = False
                self.dsm.reset(SynoSurveillanceStation.API_KEY)
                LOGGER.warning(
                    "Surveillance Station found, but disabled due to missing user"
                    " permissions"
                )

        LOGGER.debug(
            "State of Surveillance_station during setup of '%s': %s",
            self._entry.unique_id,
            self._with_surveillance_station,
        )

        # check if upgrade is available
        try:
            await self.dsm.upgrade.update()
        except SYNOLOGY_CONNECTION_EXCEPTIONS as ex:
            self._with_upgrade = False
            self.dsm.reset(SynoCoreUpgrade.API_KEY)
            LOGGER.debug("Disabled fetching upgrade data during setup: %s", ex)

        # check if file station is used and permitted
        self._with_file_station = bool(
            self.information.awesome_version >= AwesomeVersion("6.0")
            and self.dsm.apis.get(SynoFileStation.LIST_API_KEY)
        )
        if self._with_file_station:
            shares: list | None = None
            with suppress(*SYNOLOGY_CONNECTION_EXCEPTIONS):
                shares = await self.dsm.file.get_shared_folders(only_writable=True)
            if not shares:
                self._with_file_station = False
                self.dsm.reset(SynoFileStation.API_KEY)
                LOGGER.debug(
                    "File Station found, but disabled due to missing user"
                    " permissions or no writable shared folders available"
                )

            if shares and not self._entry.options.get(CONF_BACKUP_PATH):
                ir.async_create_issue(
                    self._hass,
                    DOMAIN,
                    f"{ISSUE_MISSING_BACKUP_SETUP}_{self._entry.unique_id}",
                    data={"entry_id": self._entry.entry_id},
                    is_fixable=True,
                    is_persistent=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key=ISSUE_MISSING_BACKUP_SETUP,
                    translation_placeholders={"title": self._entry.title},
                )

        LOGGER.debug(
            "State of File Station during setup of '%s': %s",
            self._entry.unique_id,
            self._with_file_station,
        )

        await self._fetch_device_configuration()

        try:
            await self._update()
        except SYNOLOGY_CONNECTION_EXCEPTIONS as err:
            LOGGER.debug(
                "Connection error during setup of '%s' with exception: %s",
                self._entry.unique_id,
                err,
            )
            raise

    @callback
    def subscribe(self, api_key: str, unique_id: str) -> Callable[[], None]:
        """Subscribe an entity to API fetches."""
        LOGGER.debug("Subscribe new entity: %s", unique_id)
        if api_key not in self._fetching_entities:
            self._fetching_entities[api_key] = set()
        self._fetching_entities[api_key].add(unique_id)

        @callback
        def unsubscribe() -> None:
            """Unsubscribe an entity from API fetches (when disable)."""
            LOGGER.debug("Unsubscribe entity: %s", unique_id)
            self._fetching_entities[api_key].remove(unique_id)
            if len(self._fetching_entities[api_key]) == 0:
                self._fetching_entities.pop(api_key)

        return unsubscribe

    def _setup_api_requests(self) -> None:
        """Determine if we should fetch each API, if one entity needs it."""
        # Entities not added yet, fetch all
        if not self._fetching_entities:
            LOGGER.debug(
                "Entities not added yet, fetch all for '%s'", self._entry.unique_id
            )
            return

        # surveillance_station is updated by own coordinator
        if self.surveillance_station:
            self.dsm.reset(self.surveillance_station)

        # Determine if we should fetch an API
        self._with_system = bool(self.dsm.apis.get(SynoCoreSystem.API_KEY))
        self._with_security = bool(
            self._fetching_entities.get(SynoCoreSecurity.API_KEY)
        )
        self._with_storage = bool(self._fetching_entities.get(SynoStorage.API_KEY))
        self._with_photos = bool(self._fetching_entities.get(SynoStorage.API_KEY))
        self._with_upgrade = bool(self._fetching_entities.get(SynoCoreUpgrade.API_KEY))
        self._with_utilisation = bool(
            self._fetching_entities.get(SynoCoreUtilization.API_KEY)
        )
        self._with_information = bool(
            self._fetching_entities.get(SynoDSMInformation.API_KEY)
        )

        # Reset not used API, information is not reset since it's used in device_info
        if not self._with_security:
            LOGGER.debug(
                "Disable security api from being updated for '%s'",
                self._entry.unique_id,
            )
            if self.security:
                self.dsm.reset(self.security)
            self.security = None

        if not self._with_file_station:
            LOGGER.debug(
                "Disable file station api from being updated or '%s'",
                self._entry.unique_id,
            )
            if self.file_station:
                self.dsm.reset(self.file_station)
            self.file_station = None

        if not self._with_photos:
            LOGGER.debug(
                "Disable photos api from being updated or '%s'", self._entry.unique_id
            )
            if self.photos:
                self.dsm.reset(self.photos)
            self.photos = None

        if not self._with_storage:
            LOGGER.debug(
                "Disable storage api from being updatedf or '%s'", self._entry.unique_id
            )
            if self.storage:
                self.dsm.reset(self.storage)
            self.storage = None

        if not self._with_system:
            LOGGER.debug(
                "Disable system api from being updated for '%s'", self._entry.unique_id
            )
            if self.system:
                self.dsm.reset(self.system)
            self.system = None

        if not self._with_upgrade:
            LOGGER.debug(
                "Disable upgrade api from being updated for '%s'", self._entry.unique_id
            )
            if self.upgrade:
                self.dsm.reset(self.upgrade)
            self.upgrade = None

        if not self._with_utilisation:
            LOGGER.debug(
                "Disable utilisation api from being updated for '%s'",
                self._entry.unique_id,
            )
            if self.utilisation:
                self.dsm.reset(self.utilisation)
            self.utilisation = None

    async def _fetch_device_configuration(self) -> None:
        """Fetch initial device config."""
        self.network = self.dsm.network
        await self.network.update()

        if self._with_file_station:
            LOGGER.debug(
                "Enable file station api updates for '%s'", self._entry.unique_id
            )
            self.file_station = self.dsm.file

        if self._with_security:
            LOGGER.debug("Enable security api updates for '%s'", self._entry.unique_id)
            self.security = self.dsm.security

        if self._with_photos:
            LOGGER.debug("Enable photos api updates for '%s'", self._entry.unique_id)
            self.photos = self.dsm.photos

        if self._with_storage:
            LOGGER.debug("Enable storage api updates for '%s'", self._entry.unique_id)
            self.storage = self.dsm.storage

        if self._with_upgrade:
            LOGGER.debug("Enable upgrade api updates for '%s'", self._entry.unique_id)
            self.upgrade = self.dsm.upgrade

        if self._with_system:
            LOGGER.debug("Enable system api updates for '%s'", self._entry.unique_id)
            self.system = self.dsm.system

        if self._with_utilisation:
            LOGGER.debug(
                "Enable utilisation api updates for '%s'", self._entry.unique_id
            )
            self.utilisation = self.dsm.utilisation

        if self._with_surveillance_station:
            LOGGER.debug(
                "Enable surveillance_station api updates for '%s'",
                self._entry.unique_id,
            )
            self.surveillance_station = self.dsm.surveillance_station

    async def _syno_api_executer(self, api_call: Callable) -> None:
        """Synology api call wrapper."""
        try:
            await api_call()
        except (SynologyDSMAPIErrorException, SynologyDSMRequestException) as err:
            LOGGER.debug(
                "Error from '%s': %s", self._entry.unique_id, err, exc_info=True
            )
            raise

    async def async_reboot(self) -> None:
        """Reboot NAS."""
        if self.system:
            await self._syno_api_executer(self.system.reboot)

    async def async_shutdown(self) -> None:
        """Shutdown NAS."""
        if self.system:
            await self._syno_api_executer(self.system.shutdown)

    async def async_unload(self) -> None:
        """Stop interacting with the NAS and prepare for removal from hass."""
        # ignore API errors during logout
        with suppress(SynologyDSMException):
            await self._syno_api_executer(self.dsm.logout)

    async def async_update(self) -> None:
        """Update function for updating API information."""
        await self._update()

    async def _update(self) -> None:
        """Update function for updating API information."""
        LOGGER.debug("Start data update for '%s'", self._entry.unique_id)
        self._setup_api_requests()
        await self.dsm.update(self._with_information)


def raise_config_entry_auth_error(err: Exception) -> None:
    """Raise ConfigEntryAuthFailed if error is related to authentication."""
    if err.args[0] and isinstance(err.args[0], dict):
        details = err.args[0].get(EXCEPTION_DETAILS, EXCEPTION_UNKNOWN)
    else:
        details = EXCEPTION_UNKNOWN
    raise ConfigEntryAuthFailed(f"reason: {details}") from err
