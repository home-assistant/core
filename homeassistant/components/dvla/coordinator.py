"""DVLA Coordinator."""

from datetime import timedelta
import logging
from typing import Any, override

from aiohttp import ClientError, ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_KEY, HOST

_LOGGER = logging.getLogger(__name__)


class DVLACoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry | None,
        session: ClientSession,
        reg_number: str,
    ) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=HOMEASSISTANT_DOMAIN,
            update_interval=timedelta(days=1),
        )
        self.session = session
        self.reg_number = str(reg_number).replace(" ", "").upper()

    @override
    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            resp = await self.session.post(
                url=HOST,
                headers={
                    "Content-Type": CONTENT_TYPE_JSON,
                    "x-api-key": API_KEY,
                },
                json={"registrationNumber": self.reg_number},
            )
            body = await resp.json()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except DVLAError as err:
            raise UpdateFailed(str(err)) from err
        except ClientError as err:
            raise UpdateFailed(str(err)) from err
        except ValueError as err:
            err_str = str(err)

            if "Invalid authentication credentials" in err_str:
                raise InvalidAuth from err
            if "API rate limit exceeded." in err_str:
                raise APIRatelimitExceeded from err

            _LOGGER.exception("Unexpected exception")
            raise UnknownError from err

        if "errors" in body:
            error = body["errors"][0]
            raise UnknownError(
                f"Error setting up {self.reg_number}: {error['title']}({error['code']}) - {error['detail']}"
            )

        if "message" in body:
            raise UnknownError(f"Error setting up {self.reg_number}: {body['message']}")

        return body


class DVLAError(HomeAssistantError):
    """Base error."""


class InvalidAuth(DVLAError):
    """Raised when invalid authentication credentials are provided."""


class APIRatelimitExceeded(DVLAError):
    """Raised when the API rate limit is exceeded."""


class UnknownError(DVLAError):
    """Raised when an unknown error occurs."""
