"""Define a custom coordinator for the Weheat heatpump integration."""

from datetime import timedelta

from weheat_backend_client.abstractions.heat_pump import HeatPump
from weheat_backend_client.exceptions import (
    ApiException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    ServiceException,
    UnauthorizedException,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import API_URL, DOMAIN, LOGGER


class WeheatDataUpdateCoordinator(DataUpdateCoordinator):
    """A custom coordinator for the Weheat heatpump integration."""

    def __init__(
        self, hass: HomeAssistant, session: OAuth2Session, heatpump_id: str | None
    ) -> None:
        """Initialize the data coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.heatpump_id: str = ""

        if heatpump_id is None:
            LOGGER.warning(
                "The weheat data coordinator cannot work if the heatpump_id is not set"
            )
        else:
            self.heatpump_id = heatpump_id

        self.session = session

    def get_it(self):
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
        except BadRequestException as e:
            LOGGER.error(
                f"The weheat integration made a bad request to the backend: {e}"
            )
        except ApiException as e:
            LOGGER.error(f"Unspecified error ocured: {e}")
        return hp

    async def _async_update_data(self):
        """Fetch data from the API."""
        await self.session.async_ensure_token_valid()

        return await self.hass.async_add_executor_job(self.get_it)
