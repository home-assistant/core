"""Number platform for IronOS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pynecil import CharSetting, CommunicationError, LiveDataResponse

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IronOSConfigEntry
from .const import DOMAIN, MAX_TEMP, MIN_TEMP
from .entity import IronOSBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IronOSNumberEntityDescription(NumberEntityDescription):
    """Describes IronOS number entity."""

    value_fn: Callable[[LiveDataResponse], float | int | None]
    max_value_fn: Callable[[LiveDataResponse], float | int]
    set_key: CharSetting


class PinecilNumber(StrEnum):
    """Number controls for Pinecil device."""

    SETPOINT_TEMP = "setpoint_temperature"


PINECIL_NUMBER_DESCRIPTIONS: tuple[IronOSNumberEntityDescription, ...] = (
    IronOSNumberEntityDescription(
        key=PinecilNumber.SETPOINT_TEMP,
        translation_key=PinecilNumber.SETPOINT_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        value_fn=lambda data: data.setpoint_temp,
        set_key=CharSetting.SETPOINT_TEMP,
        mode=NumberMode.BOX,
        native_min_value=MIN_TEMP,
        native_step=5,
        max_value_fn=lambda data: min(data.max_tip_temp_ability or MAX_TEMP, MAX_TEMP),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IronOSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        IronOSNumberEntity(coordinator, description)
        for description in PINECIL_NUMBER_DESCRIPTIONS
    )


class IronOSNumberEntity(IronOSBaseEntity, NumberEntity):
    """Implementation of a IronOS number entity."""

    entity_description: IronOSNumberEntityDescription

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        try:
            await self.coordinator.device.write(self.entity_description.set_key, value)
        except CommunicationError as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="submit_setting_failed",
            ) from e
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | int | None:
        """Return sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def native_max_value(self) -> float:
        """Return sensor state."""
        return self.entity_description.max_value_fn(self.coordinator.data)
