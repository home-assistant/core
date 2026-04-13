"""Coordinator for the Eve Online integration."""

from __future__ import annotations

import asyncio
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
    SkillQueueEntry,
    WalletBalance,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Poll intervals aligned with ESI server-side cache times.
# Polling faster than the cache window wastes API quota and quota is limited.
FAST_SCAN_INTERVAL = 60  # location/ship: 5s, wallet: 120s, mail: 30s
INDUSTRY_SCAN_INTERVAL = 300  # industry jobs, jump fatigue: 300s, skill_queue: 120s
MARKET_SCAN_INTERVAL = 3600  # market orders: 3600s
SKILLS_SCAN_INTERVAL = 86400  # character skills / total SP: 86400s


@dataclass
class EveOnlineData:
    """Fast-polling character data (location, ship, wallet, mail)."""

    character_id: int
    character_name: str
    character_online: CharacterOnlineStatus | None = None
    wallet_balance: WalletBalance | None = None
    location: CharacterLocation | None = None
    ship: CharacterShip | None = None
    mail_labels: MailLabelsSummary | None = None
    resolved_names: dict[int, str] = field(default_factory=dict)


@dataclass
class EveOnlineIndustryData:
    """Industry jobs, jump-fatigue, and skill queue data."""

    industry_jobs: list[IndustryJob] = field(default_factory=list)
    jump_fatigue: JumpFatigue | None = None
    skill_queue: list[SkillQueueEntry] = field(default_factory=list)
    resolved_names: dict[int, str] = field(default_factory=dict)


@dataclass
class EveOnlineMarketData:
    """Market orders data."""

    market_orders: list[MarketOrder] = field(default_factory=list)
    resolved_names: dict[int, str] = field(default_factory=dict)


@dataclass
class EveOnlineSkillsData:
    """Character skills / total SP data."""

    skills: CharacterSkillsSummary | None = None


class _EveOnlineBaseCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Shared base for all Eve Online coordinators."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: EveOnlineClient,
        character_id: int,
        character_name: str,
        *,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client
        self.character_id = character_id
        self.character_name = character_name

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

    async def _resolve_names(self, ids: set[int]) -> dict[int, str]:
        """Resolve numeric IDs to human-readable names in a single ESI call."""
        if not ids:
            return {}
        try:
            resolved = await self.client.async_resolve_names(list(ids))
            return {entry.id: entry.name for entry in resolved}
        except (EveOnlineError, aiohttp.ClientError) as err:
            _LOGGER.debug("Failed to resolve names: %s", err)
            return {}


class EveOnlineCoordinator(_EveOnlineBaseCoordinator[EveOnlineData]):
    """Fast coordinator (60 s): location, ship, wallet, mail, skill queue."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: EveOnlineClient,
        character_id: int,
        character_name: str,
    ) -> None:
        """Initialize the fast coordinator."""
        super().__init__(
            hass,
            entry,
            client,
            character_id,
            character_name,
            update_interval=timedelta(seconds=FAST_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> EveOnlineData:
        """Fetch fast character data from ESI."""
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

        wallet_balance, mail_labels = await asyncio.gather(
            self._fetch_optional(
                self.client.async_get_wallet_balance, self.character_id
            ),
            self._fetch_optional(self.client.async_get_mail_labels, self.character_id),
        )

        # Skip location and ship when the character is offline — those values
        # don't change while logged out, so the calls would only return the
        # last known data which we already have cached.
        location = None
        ship = None
        if character_online.online:
            location, ship = await asyncio.gather(
                self._fetch_optional(
                    self.client.async_get_character_location, self.character_id
                ),
                self._fetch_optional(
                    self.client.async_get_character_ship, self.character_id
                ),
            )

        name_ids: set[int] = set()
        if location:
            name_ids.add(location.solar_system_id)
        if ship:
            name_ids.add(ship.ship_type_id)
        resolved_names = await self._resolve_names(name_ids)

        return EveOnlineData(
            character_id=self.character_id,
            character_name=self.character_name,
            character_online=character_online,
            wallet_balance=wallet_balance,
            location=location,
            ship=ship,
            mail_labels=mail_labels,
            resolved_names=resolved_names,
        )


class EveOnlineIndustryCoordinator(_EveOnlineBaseCoordinator[EveOnlineIndustryData]):
    """Industry/fatigue/skill-queue coordinator (300 s, matching ESI cache)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: EveOnlineClient,
        character_id: int,
        character_name: str,
    ) -> None:
        """Initialize the industry coordinator."""
        super().__init__(
            hass,
            entry,
            client,
            character_id,
            character_name,
            update_interval=timedelta(seconds=INDUSTRY_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> EveOnlineIndustryData:
        """Fetch industry jobs, jump fatigue, and skill queue from ESI."""
        industry_jobs, jump_fatigue, skill_queue = await asyncio.gather(
            self._fetch_list(self.client.async_get_industry_jobs, self.character_id),
            self._fetch_optional(self.client.async_get_jump_fatigue, self.character_id),
            self._fetch_list(self.client.async_get_skill_queue, self.character_id),
        )

        name_ids: set[int] = set()
        for job in industry_jobs:
            name_ids.add(job.blueprint_type_id)
            if job.product_type_id:
                name_ids.add(job.product_type_id)
        if skill_queue:
            name_ids.add(skill_queue[0].skill_id)
        resolved_names = await self._resolve_names(name_ids)

        return EveOnlineIndustryData(
            industry_jobs=industry_jobs,
            jump_fatigue=jump_fatigue,
            skill_queue=skill_queue,
            resolved_names=resolved_names,
        )


class EveOnlineMarketCoordinator(_EveOnlineBaseCoordinator[EveOnlineMarketData]):
    """Market orders coordinator (3600 s, matching ESI cache)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: EveOnlineClient,
        character_id: int,
        character_name: str,
    ) -> None:
        """Initialize the market coordinator."""
        super().__init__(
            hass,
            entry,
            client,
            character_id,
            character_name,
            update_interval=timedelta(seconds=MARKET_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> EveOnlineMarketData:
        """Fetch market orders from ESI."""
        market_orders = await self._fetch_list(
            self.client.async_get_market_orders, self.character_id
        )

        name_ids: set[int] = {order.type_id for order in market_orders}
        resolved_names = await self._resolve_names(name_ids)

        return EveOnlineMarketData(
            market_orders=market_orders,
            resolved_names=resolved_names,
        )


class EveOnlineSkillsCoordinator(_EveOnlineBaseCoordinator[EveOnlineSkillsData]):
    """Character skills / SP coordinator (86400 s, matching ESI cache)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: EveOnlineClient,
        character_id: int,
        character_name: str,
    ) -> None:
        """Initialize the skills coordinator."""
        super().__init__(
            hass,
            entry,
            client,
            character_id,
            character_name,
            update_interval=timedelta(seconds=SKILLS_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> EveOnlineSkillsData:
        """Fetch character skills from ESI."""
        skills = await self._fetch_optional(
            self.client.async_get_skills, self.character_id
        )
        return EveOnlineSkillsData(skills=skills)


@dataclass
class EveOnlineRuntimeData:
    """Runtime data stored in the config entry."""

    coordinator: EveOnlineCoordinator
    industry_coordinator: EveOnlineIndustryCoordinator
    market_coordinator: EveOnlineMarketCoordinator
    skills_coordinator: EveOnlineSkillsCoordinator


type EveOnlineConfigEntry = ConfigEntry[EveOnlineRuntimeData]
