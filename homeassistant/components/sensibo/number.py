"""Number platform for Sensibo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pysensibo.model import SensiboDevice

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SensiboConfigEntry
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, async_handle_api_call

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SensiboNumberEntityDescription(NumberEntityDescription):
    """Class describing Sensibo Number entities."""

    remote_key: str
    value_fn: Callable[[SensiboDevice], float | None]


DEVICE_NUMBER_TYPES = (
    SensiboNumberEntityDescription(
        key="calibration_temp",
        translation_key="calibration_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        remote_key="temperature",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=-10,
        native_max_value=10,
        native_step=0.1,
        value_fn=lambda data: data.calibration_temp,
    ),
    SensiboNumberEntityDescription(
        key="calibration_hum",
        translation_key="calibration_humidity",
        device_class=NumberDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        remote_key="humidity",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=-10,
        native_max_value=10,
        native_step=0.1,
        value_fn=lambda data: data.calibration_hum,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiboConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sensibo number platform."""

    coordinator = entry.runtime_data

    async_add_entities(
        SensiboNumber(coordinator, device_id, description)
        for device_id, device_data in coordinator.data.parsed.items()
        for description in DEVICE_NUMBER_TYPES
    )


class SensiboNumber(SensiboDeviceBaseEntity, NumberEntity):
    """Representation of a Sensibo numbers."""

    entity_description: SensiboNumberEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: SensiboNumberEntityDescription,
    ) -> None:
        """Initiate Sensibo Number."""
        super().__init__(coordinator, device_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the value from coordinator data."""
        return self.entity_description.value_fn(self.device_data)

    async def async_set_native_value(self, value: float) -> None:
        """Set value for calibration."""
        await self.async_send_api_call(key=self.entity_description.key, value=value)

    @async_handle_api_call
    async def async_send_api_call(self, key: str, value: Any) -> bool:
        """Make service call to api."""
        data = {self.entity_description.remote_key: value}
        result = await self._client.async_set_calibration(
            self._device_id,
            data,
        )
        return bool(result.get("status") == "success")
