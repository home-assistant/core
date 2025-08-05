"""Vodafone Station buttons."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from json.decoder import JSONDecodeError
from typing import Any, Final

from aiovodafone.exceptions import (
    AlreadyLogged,
    CannotAuthenticate,
    CannotConnect,
    GenericLoginError,
)

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import _LOGGER, DOMAIN
from .coordinator import VodafoneConfigEntry, VodafoneStationRouter

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VodafoneStationEntityDescription(ButtonEntityDescription):
    """Vodafone Station entity description."""

    press_action: Callable[[VodafoneStationRouter], Any]
    is_suitable: Callable[[dict], bool]


BUTTON_TYPES: Final = (
    VodafoneStationEntityDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.api.restart_router(),
        is_suitable=lambda _: True,
    ),
    VodafoneStationEntityDescription(
        key="dsl_ready",
        translation_key="dsl_reconnect",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action=lambda coordinator: coordinator.api.restart_connection("dsl"),
        is_suitable=lambda info: info.get("dsl_ready") == "1",
    ),
    VodafoneStationEntityDescription(
        key="fiber_ready",
        translation_key="fiber_reconnect",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action=lambda coordinator: coordinator.api.restart_connection("fiber"),
        is_suitable=lambda info: info.get("fiber_ready") == "1",
    ),
    VodafoneStationEntityDescription(
        key="vf_internet_key_online_since",
        translation_key="internet_key_reconnect",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action=lambda coordinator: coordinator.api.restart_connection(
            "internet_key"
        ),
        is_suitable=lambda info: info.get("vf_internet_key_online_since") != "",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VodafoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up Vodafone Station buttons")

    coordinator = entry.runtime_data

    sensors_data = coordinator.data.sensors

    async_add_entities(
        VodafoneStationSensorEntity(coordinator, sensor_descr)
        for sensor_descr in BUTTON_TYPES
        if sensor_descr.is_suitable(sensors_data)
    )


class VodafoneStationSensorEntity(
    CoordinatorEntity[VodafoneStationRouter], ButtonEntity
):
    """Representation of a Vodafone Station button."""

    _attr_has_entity_name = True
    entity_description: VodafoneStationEntityDescription

    def __init__(
        self,
        coordinator: VodafoneStationRouter,
        description: VodafoneStationEntityDescription,
    ) -> None:
        """Initialize a Vodafone Station sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    async def async_press(self) -> None:
        """Triggers the Shelly button press service."""

        try:
            await self.entity_description.press_action(self.coordinator)
        except CannotAuthenticate as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_authenticate",
                translation_placeholders={"error": repr(err)},
            ) from err
        except (
            CannotConnect,
            AlreadyLogged,
            GenericLoginError,
            JSONDecodeError,
        ) as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_execute_action",
                translation_placeholders={"error": repr(err)},
            ) from err
