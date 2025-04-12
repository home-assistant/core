"""Define a custom coordinator for the Weheat heatpump integration."""

from dataclasses import dataclass
from datetime import timedelta

from weheat.abstractions.discovery import HeatPumpDiscovery
from weheat.abstractions.heat_pump import HeatPump
from weheat.exceptions import (
    ApiException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    ServiceException,
    TooManyRequestsException,
    UnauthorizedException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_URL, DOMAIN, ENERGY_UPDATE_INTERVAL, LOG_UPDATE_INTERVAL, LOGGER

type WeheatConfigEntry = ConfigEntry[list[WeheatData]]

EXCEPTIONS = (
    ServiceException,
    NotFoundException,
    ForbiddenException,
    BadRequestException,
    ApiException,
    TooManyRequestsException,
)


class HeatPumpInfo(HeatPumpDiscovery.HeatPumpInfo):
    """Heat pump info with additional properties."""

    def __init__(self, pump_info: HeatPumpDiscovery.HeatPumpInfo) -> None:
        """Initialize the HeatPump object with the provided pump information.

        Args:
            pump_info (HeatPumpDiscovery.HeatPumpInfo): An object containing the heat pump's discovery information, including:
                - uuid (str): Unique identifier for the heat pump.
                - uuid (str): Unique identifier for the heat pump.
                - device_name (str): Name of the heat pump device.
                - model (str): Model of the heat pump.
                - sn (str): Serial number of the heat pump.
                - has_dhw (bool): Indicates if the heat pump has domestic hot water functionality.

        """
        super().__init__(
            pump_info.uuid,
            pump_info.device_name,
            pump_info.model,
            pump_info.sn,
            pump_info.has_dhw,
        )

    @property
    def readable_name(self) -> str | None:
        """Return the readable name of the heat pump."""
        return self.device_name if self.device_name else self.model

    @property
    def heatpump_id(self) -> str:
        """Return the heat pump id."""
        return self.uuid


class WeheatDataUpdateCoordinator(DataUpdateCoordinator[HeatPump]):
    """A custom coordinator for the Weheat heatpump integration."""

    config_entry: WeheatConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WeheatConfigEntry,
        session: OAuth2Session,
        heat_pump: HeatPumpDiscovery.HeatPumpInfo,
        nr_of_heat_pumps: int,
    ) -> None:
        """Initialize the data coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=LOG_UPDATE_INTERVAL * nr_of_heat_pumps),
        )
        self._heat_pump_data = HeatPump(
            API_URL, heat_pump.uuid, async_get_clientsession(hass)
        )

        self.session = session

    async def _async_update_data(self) -> HeatPump:
        """Fetch data from the API."""
        await self.session.async_ensure_token_valid()

        try:
            await self._heat_pump_data.async_get_logs(
                self.session.token[CONF_ACCESS_TOKEN]
            )
        except UnauthorizedException as error:
            raise ConfigEntryAuthFailed from error
        except EXCEPTIONS as error:
            raise UpdateFailed(error) from error

        return self._heat_pump_data


class WeheatEnergyUpdateCoordinator(DataUpdateCoordinator[HeatPump]):
    """A custom Energy coordinator for the Weheat heatpump integration."""

    config_entry: WeheatConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WeheatConfigEntry,
        session: OAuth2Session,
        heat_pump: HeatPumpDiscovery.HeatPumpInfo,
    ) -> None:
        """Initialize the data coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
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


@dataclass
class WeheatData:
    """Data for the Weheat integration."""

    heat_pump_info: HeatPumpInfo
    data_coordinator: WeheatDataUpdateCoordinator
    energy_coordinator: WeheatEnergyUpdateCoordinator
