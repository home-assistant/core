"""Habitica button platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import Any

from aiohttp import ClientResponseError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HabiticaConfigEntry
from .const import DOMAIN
from .coordinator import HabiticaData, HabiticaDataUpdateCoordinator
from .entity import HabiticaBase


@dataclass(kw_only=True, frozen=True)
class HabiticaButtonEntityDescription(ButtonEntityDescription):
    """Describes Habitica button entity."""

    press_fn: Callable[[HabiticaDataUpdateCoordinator], Any]
    available_fn: Callable[[HabiticaData], bool] | None = None


class HabitipyButtonEntity(StrEnum):
    """Habitica button entities."""

    RUN_CRON = "run_cron"
    BUY_HEALTH_POTION = "buy_health_potion"
    ALLOCATE_ALL_STAT_POINTS = "allocate_all_stat_points"
    REVIVE = "revive"


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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HabiticaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons from a config entry."""

    coordinator = entry.runtime_data

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
            raise ServiceValidationError(
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
