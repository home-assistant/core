"""Coordinator for the Eve Online integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

import aiohttp
from eveonline import EveOnlineClient, EveOnlineError
from eveonline.models import CharacterLocation, WalletBalance

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = 60


@dataclass
class EveOnlineData:
    """Eve Online character data."""

    character_id: int
    character_name: str
    online: bool = False
    wallet_balance: WalletBalance | None = None
    location: CharacterLocation | None = None
    solar_system_name: str | None = None


class EveOnlineCoordinator(DataUpdateCoordinator[EveOnlineData]):
    """Coordinator for Eve Online character data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: EveOnlineClient,
        character_id: int,
        character_name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.client = client
        self.character_id = character_id
        self.character_name = character_name

    async def _async_update_data(self) -> EveOnlineData:
        """Fetch character data from ESI."""
        try:
            character_online = await self.client.async_get_character_online(
                self.character_id
            )
        except (EveOnlineError, aiohttp.ClientError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        wallet_balance: WalletBalance | None = None
        try:
            wallet_balance = await self.client.async_get_wallet_balance(
                self.character_id
            )
        except (EveOnlineError, aiohttp.ClientError) as err:
            _LOGGER.debug("Failed to fetch wallet balance: %s", err)

        location: CharacterLocation | None = None
        solar_system_name: str | None = None
        try:
            location = await self.client.async_get_character_location(self.character_id)
        except (EveOnlineError, aiohttp.ClientError) as err:
            _LOGGER.debug("Failed to fetch location: %s", err)

        if location:
            try:
                resolved = await self.client.async_resolve_names(
                    [location.solar_system_id]
                )
                if resolved:
                    solar_system_name = resolved[0].name
            except (EveOnlineError, aiohttp.ClientError) as err:
                _LOGGER.debug("Failed to resolve solar system name: %s", err)

        return EveOnlineData(
            character_id=self.character_id,
            character_name=self.character_name,
            online=character_online.online,
            wallet_balance=wallet_balance,
            location=location,
            solar_system_name=solar_system_name,
        )


type EveOnlineConfigEntry = ConfigEntry[EveOnlineCoordinator]
