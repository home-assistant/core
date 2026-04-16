"""Coordinator for the Eve Online integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

import aiohttp
from eveonline import EveOnlineClient, EveOnlineError
from eveonline.models import CharacterLocation, CharacterShip

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type EveOnlineConfigEntry = ConfigEntry[EveOnlineCoordinator]


@dataclass(slots=True, kw_only=True)
class EveOnlineData:
    """Eve Online character data."""

    character_id: int
    character_name: str
    wallet_balance: float | None = None
    location: CharacterLocation | None = None
    solar_system_name: str | None = None
    ship: CharacterShip | None = None
    ship_type_name: str | None = None


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
            update_interval=timedelta(minutes=1),
        )
        self.client = client
        self.character_id = character_id
        self.character_name = character_name

    async def _async_update_data(self) -> EveOnlineData:
        """Fetch character data from ESI."""
        try:
            wallet = await self.client.async_get_wallet_balance(self.character_id)
        except (EveOnlineError, aiohttp.ClientError) as err:
            raise UpdateFailed(
                f"Error communicating with Eve Online API: {err}"
            ) from err

        location: CharacterLocation | None = None
        ship: CharacterShip | None = None
        try:
            location, ship = await asyncio.gather(
                self.client.async_get_character_location(self.character_id),
                self.client.async_get_character_ship(self.character_id),
            )
        except (EveOnlineError, aiohttp.ClientError) as err:
            _LOGGER.debug("Failed to fetch location or ship: %s", err)

        solar_system_name: str | None = None
        ship_type_name: str | None = None

        ids_to_resolve = []
        if location:
            ids_to_resolve.append(location.solar_system_id)
        if ship:
            ids_to_resolve.append(ship.ship_type_id)

        if ids_to_resolve:
            try:
                resolved = await self.client.async_resolve_names(ids_to_resolve)
                resolved_by_id = {r.id: r.name for r in resolved}
                if location:
                    solar_system_name = resolved_by_id.get(location.solar_system_id)
                if ship:
                    ship_type_name = resolved_by_id.get(ship.ship_type_id)
            except (EveOnlineError, aiohttp.ClientError) as err:
                _LOGGER.debug("Failed to resolve names: %s", err)

        return EveOnlineData(
            character_id=self.character_id,
            character_name=self.character_name,
            wallet_balance=wallet.balance,
            location=location,
            solar_system_name=solar_system_name,
            ship=ship,
            ship_type_name=ship_type_name,
        )
