"""Switch platform for Habitica integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from aiohttp import ClientResponseError

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HabiticaConfigEntry
from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import HabiticaData, HabiticaDataUpdateCoordinator


@dataclass(kw_only=True, frozen=True)
class HabiticaSwitchEntityDescription(SwitchEntityDescription):
    """Describes Habitica switch entity."""

    turn_on_fn: Callable[[HabiticaDataUpdateCoordinator], Any]
    turn_off_fn: Callable[[HabiticaDataUpdateCoordinator], Any]
    is_on_fn: Callable[[HabiticaData], bool]


class HabiticaSwitchEntity(StrEnum):
    """Habitica switch entities."""

    SLEEP = "sleep"


SWTICH_DESCRIPTIONS: tuple[HabiticaSwitchEntityDescription, ...] = (
    HabiticaSwitchEntityDescription(
        key=HabiticaSwitchEntity.SLEEP,
        translation_key=HabiticaSwitchEntity.SLEEP,
        device_class=SwitchDeviceClass.SWITCH,
        turn_on_fn=lambda coordinator: coordinator.api["user"]["sleep"].post(),
        turn_off_fn=lambda coordinator: coordinator.api["user"]["sleep"].post(),
        is_on_fn=lambda data: data.user["preferences"]["sleep"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HabiticaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches from a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        HabiticaSwitch(coordinator, description) for description in SWTICH_DESCRIPTIONS
    )


class HabiticaSwitch(CoordinatorEntity[HabiticaDataUpdateCoordinator], SwitchEntity):
    """Representation of a Habitica Switch."""

    _attr_has_entity_name = True
    entity_description: HabiticaSwitchEntityDescription

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
        entity_description: HabiticaSwitchEntityDescription,
    ) -> None:
        """Initialize a Habitica switch."""
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

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.entity_description.is_on_fn(
            self.coordinator.data,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self.entity_description.turn_on_fn(self.coordinator)
        except ClientResponseError as e:
            if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="setup_rate_limit_exception",
                ) from e
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        else:
            await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            await self.entity_description.turn_off_fn(self.coordinator)
        except ClientResponseError as e:
            if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="setup_rate_limit_exception",
                ) from e
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        else:
            await self.coordinator.async_refresh()
