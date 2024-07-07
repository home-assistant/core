"""Habitica button platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from aiohttp import ClientResponseError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HabiticaConfigEntry
from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import HabiticaData, HabiticaDataUpdateCoordinator


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
        press_fn=(lambda coordinator: coordinator.api["user"]["allocate-now"].post()),
        available_fn=(
            lambda data: data.user["preferences"].get("automaticAllocation") is True
            and data.user["stats"]["points"] > 0
        ),
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


class HabiticaButton(CoordinatorEntity[HabiticaDataUpdateCoordinator], ButtonEntity):
    """Representation of a Habitica button."""

    _attr_has_entity_name = True
    entity_description: HabiticaButtonEntityDescription

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
        entity_description: HabiticaButtonEntityDescription,
    ) -> None:
        """Initialize a Habitica button."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            name=coordinator.config_entry.data[CONF_NAME],
            configuration_url=coordinator.config_entry.data[CONF_URL],
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
        )

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

    @property
    def available(self) -> bool:
        """Is entity available."""
        if self.entity_description.available_fn:
            return self.entity_description.available_fn(self.coordinator.data)
        return True
