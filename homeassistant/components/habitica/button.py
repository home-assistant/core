"""Habitica button platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import Any

from aiohttp import ClientResponseError

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ASSETS_URL, DOMAIN, HEALER, MAGE, ROGUE, WARRIOR
from .coordinator import HabiticaData, HabiticaDataUpdateCoordinator
from .entity import HabiticaBase
from .types import HabiticaConfigEntry

PARALLEL_UPDATES = 1


@dataclass(kw_only=True, frozen=True)
class HabiticaButtonEntityDescription(ButtonEntityDescription):
    """Describes Habitica button entity."""

    press_fn: Callable[[HabiticaDataUpdateCoordinator], Any]
    available_fn: Callable[[HabiticaData], bool] | None = None
    class_needed: str | None = None
    entity_picture: str | None = None


class HabitipyButtonEntity(StrEnum):
    """Habitica button entities."""

    RUN_CRON = "run_cron"
    BUY_HEALTH_POTION = "buy_health_potion"
    ALLOCATE_ALL_STAT_POINTS = "allocate_all_stat_points"
    REVIVE = "revive"
    MPHEAL = "mpheal"
    EARTH = "earth"
    FROST = "frost"
    DEFENSIVE_STANCE = "defensive_stance"
    VALOROUS_PRESENCE = "valorous_presence"
    INTIMIDATE = "intimidate"
    TOOLS_OF_TRADE = "tools_of_trade"
    STEALTH = "stealth"
    HEAL = "heal"
    PROTECT_AURA = "protect_aura"
    BRIGHTNESS = "brightness"
    HEAL_ALL = "heal_all"


BUTTON_DESCRIPTIONS: tuple[HabiticaButtonEntityDescription, ...] = (
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.RUN_CRON,
        translation_key=HabitipyButtonEntity.RUN_CRON,
        press_fn=lambda coordinator: coordinator.api.cron.post(),
        available_fn=lambda data: data.user["needsCron"],
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.BUY_HEALTH_POTION,
        translation_key=HabitipyButtonEntity.BUY_HEALTH_POTION,
        press_fn=(
            lambda coordinator: coordinator.api["user"]["buy-health-potion"].post()
        ),
        available_fn=(
            lambda data: data.user["stats"]["gp"] >= 25
            and data.user["stats"]["hp"] < 50
        ),
        entity_picture="shop_potion.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.ALLOCATE_ALL_STAT_POINTS,
        translation_key=HabitipyButtonEntity.ALLOCATE_ALL_STAT_POINTS,
        press_fn=lambda coordinator: coordinator.api["user"]["allocate-now"].post(),
        available_fn=(
            lambda data: data.user["preferences"].get("automaticAllocation") is True
            and data.user["stats"]["points"] > 0
        ),
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.REVIVE,
        translation_key=HabitipyButtonEntity.REVIVE,
        press_fn=lambda coordinator: coordinator.api["user"]["revive"].post(),
        available_fn=lambda data: data.user["stats"]["hp"] == 0,
    ),
)


CLASS_SKILLS: tuple[HabiticaButtonEntityDescription, ...] = (
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.MPHEAL,
        translation_key=HabitipyButtonEntity.MPHEAL,
        press_fn=lambda coordinator: coordinator.api.user.class_.cast["mpheal"].post(),
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 12
            and data.user["stats"]["mp"] >= 30
        ),
        class_needed=MAGE,
        entity_picture="shop_mpheal.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.EARTH,
        translation_key=HabitipyButtonEntity.EARTH,
        press_fn=lambda coordinator: coordinator.api.user.class_.cast["earth"].post(),
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 13
            and data.user["stats"]["mp"] >= 35
        ),
        class_needed=MAGE,
        entity_picture="shop_earth.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.FROST,
        translation_key=HabitipyButtonEntity.FROST,
        press_fn=lambda coordinator: coordinator.api.user.class_.cast["frost"].post(),
        # chilling frost can only be cast once per day (streaks buff is false)
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 14
            and data.user["stats"]["mp"] >= 40
            and not data.user["stats"]["buffs"]["streaks"]
        ),
        class_needed=MAGE,
        entity_picture="shop_frost.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.DEFENSIVE_STANCE,
        translation_key=HabitipyButtonEntity.DEFENSIVE_STANCE,
        press_fn=(
            lambda coordinator: coordinator.api.user.class_.cast[
                "defensiveStance"
            ].post()
        ),
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 12
            and data.user["stats"]["mp"] >= 25
        ),
        class_needed=WARRIOR,
        entity_picture="shop_defensiveStance.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.VALOROUS_PRESENCE,
        translation_key=HabitipyButtonEntity.VALOROUS_PRESENCE,
        press_fn=(
            lambda coordinator: coordinator.api.user.class_.cast[
                "valorousPresence"
            ].post()
        ),
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 13
            and data.user["stats"]["mp"] >= 20
        ),
        class_needed=WARRIOR,
        entity_picture="shop_valorousPresence.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.INTIMIDATE,
        translation_key=HabitipyButtonEntity.INTIMIDATE,
        press_fn=(
            lambda coordinator: coordinator.api.user.class_.cast["intimidate"].post()
        ),
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 14
            and data.user["stats"]["mp"] >= 15
        ),
        class_needed=WARRIOR,
        entity_picture="shop_intimidate.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.TOOLS_OF_TRADE,
        translation_key=HabitipyButtonEntity.TOOLS_OF_TRADE,
        press_fn=(
            lambda coordinator: coordinator.api.user.class_.cast["toolsOfTrade"].post()
        ),
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 13
            and data.user["stats"]["mp"] >= 25
        ),
        class_needed=ROGUE,
        entity_picture="shop_toolsOfTrade.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.STEALTH,
        translation_key=HabitipyButtonEntity.STEALTH,
        press_fn=(
            lambda coordinator: coordinator.api.user.class_.cast["stealth"].post()
        ),
        # Stealth buffs stack and it can only be cast if the amount of
        # unfinished dailies is smaller than the amount of buffs
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 14
            and data.user["stats"]["mp"] >= 45
            and data.user["stats"]["buffs"]["stealth"]
            < len(
                [
                    r
                    for r in data.tasks
                    if r.get("type") == "daily"
                    and r.get("isDue") is True
                    and r.get("completed") is False
                ]
            )
        ),
        class_needed=ROGUE,
        entity_picture="shop_stealth.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.HEAL,
        translation_key=HabitipyButtonEntity.HEAL,
        press_fn=lambda coordinator: coordinator.api.user.class_.cast["heal"].post(),
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 11
            and data.user["stats"]["mp"] >= 15
            and data.user["stats"]["hp"] < 50
        ),
        class_needed=HEALER,
        entity_picture="shop_heal.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.BRIGHTNESS,
        translation_key=HabitipyButtonEntity.BRIGHTNESS,
        press_fn=(
            lambda coordinator: coordinator.api.user.class_.cast["brightness"].post()
        ),
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 12
            and data.user["stats"]["mp"] >= 15
        ),
        class_needed=HEALER,
        entity_picture="shop_brightness.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.PROTECT_AURA,
        translation_key=HabitipyButtonEntity.PROTECT_AURA,
        press_fn=(
            lambda coordinator: coordinator.api.user.class_.cast["protectAura"].post()
        ),
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 13
            and data.user["stats"]["mp"] >= 30
        ),
        class_needed=HEALER,
        entity_picture="shop_protectAura.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabitipyButtonEntity.HEAL_ALL,
        translation_key=HabitipyButtonEntity.HEAL_ALL,
        press_fn=lambda coordinator: coordinator.api.user.class_.cast["healAll"].post(),
        available_fn=(
            lambda data: data.user["stats"]["lvl"] >= 14
            and data.user["stats"]["mp"] >= 25
        ),
        class_needed=HEALER,
        entity_picture="shop_healAll.png",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HabiticaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons from a config entry."""

    coordinator = entry.runtime_data
    skills_added: set[str] = set()

    @callback
    def add_entities() -> None:
        """Add or remove a skillset based on the player's class."""

        nonlocal skills_added
        buttons = []
        entity_registry = er.async_get(hass)

        for description in CLASS_SKILLS:
            if (
                coordinator.data.user["stats"]["lvl"] >= 10
                and coordinator.data.user["flags"]["classSelected"]
                and not coordinator.data.user["preferences"]["disableClasses"]
                and description.class_needed == coordinator.data.user["stats"]["class"]
            ):
                if description.key not in skills_added:
                    buttons.append(HabiticaButton(coordinator, description))
                    skills_added.add(description.key)
            elif description.key in skills_added:
                if entity_id := entity_registry.async_get_entity_id(
                    BUTTON_DOMAIN,
                    DOMAIN,
                    f"{coordinator.config_entry.unique_id}_{description.key}",
                ):
                    entity_registry.async_remove(entity_id)
                skills_added.remove(description.key)

        if buttons:
            async_add_entities(buttons)

    coordinator.async_add_listener(add_entities)
    add_entities()

    async_add_entities(
        HabiticaButton(coordinator, description) for description in BUTTON_DESCRIPTIONS
    )


class HabiticaButton(HabiticaBase, ButtonEntity):
    """Representation of a Habitica button."""

    entity_description: HabiticaButtonEntityDescription

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.entity_description.press_fn(self.coordinator)
        except ClientResponseError as e:
            if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="setup_rate_limit_exception",
                ) from e
            if e.status == HTTPStatus.UNAUTHORIZED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="service_call_unallowed",
                ) from e
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        else:
            await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        """Is entity available."""
        if not super().available:
            return False
        if self.entity_description.available_fn:
            return self.entity_description.available_fn(self.coordinator.data)
        return True

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        if entity_picture := self.entity_description.entity_picture:
            return f"{ASSETS_URL}{entity_picture}"
        return None
