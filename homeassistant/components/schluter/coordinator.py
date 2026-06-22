"""DataUpdateCoordinator for the Schluter DITRA-HEAT integration."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CannotConnectError,
    InvalidCredentialsError,
    InvalidSessionError,
    SchluterApi,
    SchluterThermostat,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type SchluterConfigEntry = ConfigEntry[SchluterCoordinator]


class SchluterCoordinator(DataUpdateCoordinator[dict[str, SchluterThermostat]]):
    """Coordinator that fetches thermostat data and manages the session token."""

    config_entry: SchluterConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: SchluterApi, entry: SchluterConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=3),
        )
        self.api = api
        self.session_id: str = ""

    async def _async_setup(self) -> None:
        """Authenticate on first setup; called once before the first refresh."""
        await self._async_authenticate()

    async def _async_update_data(self) -> dict[str, SchluterThermostat]:
        """Fetch thermostat data, re-authenticating silently if the session expired."""
        try:
            thermostats = await self.api.async_get_thermostats(self.session_id)
        except InvalidSessionError:
            await self._async_authenticate()
            try:
                thermostats = await self.api.async_get_thermostats(self.session_id)
            except InvalidSessionError as err:
                raise ConfigEntryAuthFailed from err
            except CannotConnectError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN, translation_key="update_failed"
                ) from err
        except CannotConnectError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err

        return {t.serial_number: t for t in thermostats}

    async def _async_authenticate(self) -> None:
        """Obtain a new session token using stored credentials."""
        username = self.config_entry.data[CONF_USERNAME]
        password = self.config_entry.data[CONF_PASSWORD]
        try:
            self.session_id = await self.api.async_get_session(username, password)
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed from err
        except CannotConnectError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err
