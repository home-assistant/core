"""Coordinator for the Eve Online integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

import aiohttp
from eveonline import EveOnlineClient, EveOnlineError
from eveonline.models import (
    CharacterLocation,
    CharacterOnlineStatus,
    CharacterShip,
    CharacterSkillsSummary,
    IndustryJob,
    JumpFatigue,
    MailLabelsSummary,
    MarketOrder,
    ServerStatus,
    SkillQueueEntry,
    WalletBalance,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = 60


@dataclass
class EveOnlineData:
    """Combined server and character data."""

    server_status: ServerStatus
    character_id: int
    character_name: str
    character_online: CharacterOnlineStatus | None = None
    wallet_balance: WalletBalance | None = None
    skill_queue: list[SkillQueueEntry] = field(default_factory=list)
    location: CharacterLocation | None = None
    ship: CharacterShip | None = None
    skills: CharacterSkillsSummary | None = None
    mail_labels: MailLabelsSummary | None = None
    industry_jobs: list[IndustryJob] = field(default_factory=list)
    market_orders: list[MarketOrder] = field(default_factory=list)
    jump_fatigue: JumpFatigue | None = None
    resolved_names: dict[int, str] = field(default_factory=dict)


type EveOnlineConfigEntry = ConfigEntry[EveOnlineCoordinator]


class EveOnlineCoordinator(DataUpdateCoordinator[EveOnlineData]):
    """Coordinator to poll Eve Online server and character data."""

    config_entry: EveOnlineConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EveOnlineConfigEntry,
        client: EveOnlineClient,
        character_id: int,
        character_name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.client = client
        self.character_id = character_id
        self.character_name = character_name

    async def _async_update_data(self) -> EveOnlineData:
        """Fetch server status and character data from ESI."""
        try:
            server_status = await self.client.async_get_server_status()
        except (EveOnlineError, aiohttp.ClientError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        character_online = await self._fetch_optional(
            self.client.async_get_character_online, self.character_id
        )
        wallet_balance = await self._fetch_optional(
            self.client.async_get_wallet_balance, self.character_id
        )
        skill_queue = await self._fetch_list(
            self.client.async_get_skill_queue, self.character_id
        )
        location = await self._fetch_optional(
            self.client.async_get_character_location, self.character_id
        )
        ship = await self._fetch_optional(
            self.client.async_get_character_ship, self.character_id
        )
        skills = await self._fetch_optional(
            self.client.async_get_skills, self.character_id
        )
        mail_labels = await self._fetch_optional(
            self.client.async_get_mail_labels, self.character_id
        )
        industry_jobs = await self._fetch_list(
            self.client.async_get_industry_jobs, self.character_id
        )
        market_orders = await self._fetch_list(
            self.client.async_get_market_orders, self.character_id
        )
        jump_fatigue = await self._fetch_optional(
            self.client.async_get_jump_fatigue, self.character_id
        )

        resolved_names = await self._resolve_names(
            location, ship, skill_queue, industry_jobs, market_orders
        )

        return EveOnlineData(
            server_status=server_status,
            character_id=self.character_id,
            character_name=self.character_name,
            character_online=character_online,
            wallet_balance=wallet_balance,
            skill_queue=skill_queue,
            location=location,
            ship=ship,
            skills=skills,
            mail_labels=mail_labels,
            industry_jobs=industry_jobs,
            market_orders=market_orders,
            jump_fatigue=jump_fatigue,
            resolved_names=resolved_names,
        )

    async def _fetch_optional[T](
        self,
        method: Callable[..., Awaitable[T]],
        *args: Any,
    ) -> T | None:
        """Fetch an optional endpoint, returning None on failure."""
        try:
            return await method(*args)
        except (EveOnlineError, aiohttp.ClientError) as err:
            _LOGGER.debug("Failed to fetch %s: %s", method.__name__, err)
            return None

    async def _fetch_list[T](
        self,
        method: Callable[..., Awaitable[list[T]]],
        *args: Any,
    ) -> list[T]:
        """Fetch a list endpoint, returning empty list on failure."""
        try:
            return await method(*args)
        except (EveOnlineError, aiohttp.ClientError) as err:
            _LOGGER.debug("Failed to fetch %s: %s", method.__name__, err)
            return []

    async def _resolve_names(
        self,
        location: CharacterLocation | None,
        ship: CharacterShip | None,
        skill_queue: list[SkillQueueEntry],
        industry_jobs: list[IndustryJob],
        market_orders: list[MarketOrder],
    ) -> dict[int, str]:
        """Resolve numeric IDs to human-readable names in a single API call."""
        ids: set[int] = set()

        if location:
            ids.add(location.solar_system_id)
        if ship:
            ids.add(ship.ship_type_id)
        if skill_queue:
            ids.add(skill_queue[0].skill_id)
        for job in industry_jobs:
            ids.add(job.blueprint_type_id)
            if job.product_type_id:
                ids.add(job.product_type_id)
        for order in market_orders:
            ids.add(order.type_id)

        if not ids:
            return {}

        try:
            resolved = await self.client.async_resolve_names(list(ids))
            return {entry.id: entry.name for entry in resolved}
        except (EveOnlineError, aiohttp.ClientError) as err:
            _LOGGER.debug("Failed to resolve names: %s", err)
            return {}
