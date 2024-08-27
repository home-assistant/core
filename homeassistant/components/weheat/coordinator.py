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

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import API_URL, DOMAIN, LOGGER, UPDATE_INTERVAL


class WeheatDataUpdateCoordinator(DataUpdateCoordinator[HeatPump]):
    """A custom coordinator for the Weheat heatpump integration."""

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
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self._heat_pump = heat_pump

        self.session = session

    @property
    def heatpump_id(self) -> str:
        """Return the heat pump id."""
        return self._heat_pump.uuid

    @property
    def readable_name(self) -> str | None:
        """Return the readable name of the heat pump."""
        return self._heat_pump.name

    @property
    def model(self) -> str:
        """Return the model of the heat pump."""
        return self._heat_pump.model

    def fetch_data(self) -> HeatPump:
        """Get the data from the API."""
        token = self.session.token["access_token"]

        hp = HeatPump(API_URL, self.heatpump_id)

        try:
            hp.get_status(token)
        except ServiceException as e:
            LOGGER.error(f"Weheat backend has had an internal error: {e}")
        except NotFoundException as e:
            LOGGER.error(f"Could not find the heat pump by id: {e}")
        except ForbiddenException as e:
            LOGGER.error(f"The actions was not allowed by the backend: {e}")
        except UnauthorizedException as e:
            LOGGER.error(f"The user was not authorized to access this information: {e}")
            # also make the user re-authenticate
            raise ConfigEntryAuthFailed("Unauthorized access to the Weheat API") from e
        except BadRequestException as e:
            LOGGER.error(
                f"The weheat integration made a bad request to the backend: {e}"
            )
        except ApiException as e:
            LOGGER.error(f"Unspecified error ocured: {e}")
        return hp

    async def _async_update_data(self) -> HeatPump:
        """Fetch data from the API."""
        await self.session.async_ensure_token_valid()

        return await self.hass.async_add_executor_job(self.fetch_data)
