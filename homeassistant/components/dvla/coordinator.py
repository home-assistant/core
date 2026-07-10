"""DVLA Coordinator."""

from datetime import timedelta
import logging
from typing import Any, override

from aiohttp import ClientError, ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch vehicle data from the DVLA API."""
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
        except ClientError as err:
            raise UpdateFailed(str(err)) from err
        except ValueError as err:
            raise UpdateFailed("Invalid response from DVLA API") from err

        if resp.status in (401, 403):
            raise ConfigEntryAuthFailed("Invalid authentication credentials")

        if resp.status == 429:
            raise UpdateFailed("DVLA API rate limit exceeded")

        if "errors" in body:
            error = body["errors"][0]
            raise UpdateFailed(
                f"Error setting up {self.reg_number}: "
                f"{error.get('title')}({error.get('code')}) - {error.get('detail')}"
            )

        if "message" in body:
            message = str(body["message"])
            if "Invalid authentication credentials" in message:
                raise ConfigEntryAuthFailed(message)
            if "API rate limit exceeded" in message:
                raise UpdateFailed(message)
            raise UpdateFailed(f"Error setting up {self.reg_number}: {message}")

        if resp.status >= 400:
            raise UpdateFailed(f"DVLA lookup failed with status {resp.status}: {body}")

        return body
