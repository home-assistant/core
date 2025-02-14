"""Define a custom coordinator for the Weheat heatpump integration."""

from datetime import timedelta

from weheat.abstractions.discovery import HeatPumpDiscovery
from weheat.abstractions.heat_pump import HeatPump
from weheat.exceptions import (
    ApiException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    ServiceException,
    UnauthorizedException,
)

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_URL, DOMAIN, LOGGER, LOG_UPDATE_INTERVAL, ENERGY_UPDATE_INTERVAL

EXCEPTIONS = (
    ServiceException,
    NotFoundException,
    ForbiddenException,
    BadRequestException,
    ApiException,
)


class WeheatDataUpdateCoordinator(DataUpdateCoordinator[HeatPump]):
    """A custom coordinator for the Weheat heatpump integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: OAuth2Session,
        heat_pump: HeatPumpDiscovery.HeatPumpInfo,
        nr_of_heat_pumps: int,
    ) -> None:
        """Initialize the data coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=LOG_UPDATE_INTERVAL) * nr_of_heat_pumps,
        )
        self._heat_pump_data = HeatPump(
            API_URL, heat_pump.uuid, async_get_clientsession(hass)
        )

        self.session = session


    async def _async_update_data(self) -> HeatPump:
        """Fetch data from the API."""
        await self.session.async_ensure_token_valid()

        try:
            await self._heat_pump_data.async_get_status(
                self.session.token[CONF_ACCESS_TOKEN]
            )
        except UnauthorizedException as error:
            raise ConfigEntryAuthFailed from error
        except EXCEPTIONS as error:
            raise UpdateFailed(error) from error

        return self._heat_pump_data


class WeheatEnergyUpdateCoordinator(DataUpdateCoordinator[HeatPump]):
    """A custom Energy coordinator for the Weheat heatpump integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: OAuth2Session,
        heat_pump: HeatPumpDiscovery.HeatPumpInfo,
    ) -> None:
        """Initialize the data coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=ENERGY_UPDATE_INTERVAL),
        )
        self._heat_pump_data = HeatPump(
            API_URL, heat_pump.uuid, async_get_clientsession(hass)
        )

        self.session = session


    async def _async_update_data(self) -> HeatPump:
        """Fetch data from the API."""
        await self.session.async_ensure_token_valid()

        try:
            await self._heat_pump_data.async_get_energy(
                self.session.token[CONF_ACCESS_TOKEN]
            )
        except UnauthorizedException as error:
            raise ConfigEntryAuthFailed from error
        except EXCEPTIONS as error:
            raise UpdateFailed(error) from error

        return self._heat_pump_data
