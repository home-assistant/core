"""Number platform for Sensibo integration."""
from __future__ import annotations

import asyncio

from aiohttp.client_exceptions import ClientConnectionError
import async_timeout
from pysensibo.exceptions import AuthenticationError, SensiboError

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, TIMEOUT
from .coordinator import SensiboDataUpdateCoordinator

NUMBER_TYPES: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="calibration_temp",
        name="Temperature calibration",
        icon="mdi:thermometer",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        min_value=-10,
        max_value=10,
        step=1,
    ),
    NumberEntityDescription(
        key="calibration_hum",
        name="Humidity calibration",
        icon="mdi:water",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        min_value=-10,
        max_value=10,
        step=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo number platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        [
            SensiboNumber(coordinator, device_id, description)
            for device_id, device_data in coordinator.data.items()
            if device_data["hvac_modes"] and device_data["temp"]
        ]
        for description in NUMBER_TYPES
    ]
    async_add_entities(entities)


class SensiboNumber(CoordinatorEntity, NumberEntity):
    """Representation of a Sensibo numbers."""

    coordinator: SensiboDataUpdateCoordinator
    entity_description: NumberEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: NumberEntityDescription,
    ) -> None:
        """Initiate Sensibo Number."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._device_id = device_id
        self._client = coordinator.client
        self._attr_unique_id = f"{device_id} {entity_description.key}"
        self._attr_name = (
            f"{coordinator.data[device_id]['name']} {entity_description.name}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data[device_id]["id"])},
            name=coordinator.data[device_id]["name"],
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=coordinator.data[device_id]["model"],
            sw_version=coordinator.data[device_id]["fw_ver"],
            hw_version=coordinator.data[device_id]["fw_type"],
            suggested_area=coordinator.data[device_id]["name"],
        )

    @property
    def value(self) -> float:
        """Return the value from coordinator data."""
        return self.coordinator.data[self._device_id][self.entity_description.key]

    async def async_set_value(self, value: float) -> None:
        """Set value not implemented."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                result = await self._client.async_set_calibration(
                    self.unique_id,
                    value,
                )
        except (
            ClientConnectionError,
            asyncio.TimeoutError,
            AuthenticationError,
            SensiboError,
        ) as err:
            raise HomeAssistantError(
                f"Failed to set calibration for device {self.name} to Sensibo servers: {err}"
            ) from err
        LOGGER.debug("Result: %s", result)
        if result["status"] == "Success":
            return

        failure = result["failureReason"]
        raise HomeAssistantError(
            f"Could not set calibration for device {self.name} due to reason {failure}"
        )
