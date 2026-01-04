"""Define the Nanoleaf data coordinator."""

from datetime import timedelta
import logging

import aiohttp
from aionanoleaf import InvalidToken, Nanoleaf, Unavailable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ESSENTIALS_MODEL_PREFIXES

_LOGGER = logging.getLogger(__name__)

type NanoleafConfigEntry = ConfigEntry[NanoleafCoordinator]


class NanoleafCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Nanoleaf data."""

    config_entry: NanoleafConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: NanoleafConfigEntry, nanoleaf: Nanoleaf
    ) -> None:
        """Initialize the Nanoleaf data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Nanoleaf",
            update_interval=timedelta(minutes=1),
        )
        self.nanoleaf = nanoleaf
        self._token = config_entry.data[CONF_TOKEN]
        # Effects data for Essentials devices (fetched via direct HTTP)
        self.essentials_effects_list: list[str] | None = None
        self.essentials_current_effect: str | None = None

    @property
    def is_essentials(self) -> bool:
        """Return True if this is an Essentials device."""
        model = self.nanoleaf.model or ""
        return model.startswith(ESSENTIALS_MODEL_PREFIXES)

    async def _fetch_essentials_effects(self) -> None:
        """Fetch effects for Essentials devices via direct HTTP.

        Essentials devices use a different API for effects than Panels.
        We make direct HTTP calls to fetch animations list and current effect.
        """
        session = async_get_clientsession(self.hass)
        base_url = (
            f"http://{self.nanoleaf.host}:{self.nanoleaf.port}/api/v1/{self._token}"
        )

        try:
            # Get animations list via Command API
            async with session.put(
                f"{base_url}/effects",
                json={"write": {"command": "requestAll"}},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.essentials_effects_list = [
                        anim["animName"] for anim in data.get("animations", [])
                    ]

            # Get current effect
            async with session.get(f"{base_url}/effects/select") as resp:
                if resp.status == 200:
                    text = await resp.text()
                    # Response may be quoted, strip quotes
                    self.essentials_current_effect = text.strip().strip('"')
        except (TimeoutError, aiohttp.ClientError):
            _LOGGER.debug("Failed to fetch Essentials effects", exc_info=True)

    async def _async_update_data(self) -> None:
        try:
            await self.nanoleaf.get_info()
            # Fetch effects for Essentials devices via direct HTTP
            if self.is_essentials:
                await self._fetch_essentials_effects()
        except Unavailable as err:
            raise UpdateFailed from err
        except InvalidToken as err:
            raise ConfigEntryAuthFailed from err
