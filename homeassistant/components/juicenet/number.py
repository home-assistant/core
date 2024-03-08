"""Support for controlling juicenet/juicepoint/juicebox based EVSE numbers."""
from __future__ import annotations

from dataclasses import dataclass

from pyjuicenet import Api, Charger

from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, JUICENET_API, JUICENET_COORDINATOR
from .entity import JuiceNetDevice


@dataclass(frozen=True)
class JuiceNetNumberEntityDescriptionMixin:
    """Mixin for required keys."""

    setter_key: str


@dataclass(frozen=True)
class JuiceNetNumberEntityDescription(
    NumberEntityDescription, JuiceNetNumberEntityDescriptionMixin
):
    """An entity description for a JuiceNetNumber."""

    native_max_value_key: str | None = None


NUMBER_TYPES: tuple[JuiceNetNumberEntityDescription, ...] = (
    JuiceNetNumberEntityDescription(
        translation_key="amperage_limit",
        key="current_charging_amperage_limit",
        native_min_value=6,
        native_max_value_key="max_charging_amperage",
        native_step=1,
        setter_key="set_charging_amperage_limit",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the JuiceNet Numbers."""
    juicenet_data = hass.data[DOMAIN][config_entry.entry_id]
    api: Api = juicenet_data[JUICENET_API]
    coordinator = juicenet_data[JUICENET_COORDINATOR]

    entities = [
        JuiceNetNumber(device, description, coordinator)
        for device in api.devices
        for description in NUMBER_TYPES
    ]
    async_add_entities(entities)


class JuiceNetNumber(JuiceNetDevice, NumberEntity):
    """Implementation of a JuiceNet number."""

    entity_description: JuiceNetNumberEntityDescription

    def __init__(
        self,
        device: Charger,
        description: JuiceNetNumberEntityDescription,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialise the number."""
        super().__init__(device, description.key, coordinator)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the value of the entity."""
        return getattr(self.device, self.entity_description.key, None)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        if self.entity_description.native_max_value_key is not None:
            return getattr(self.device, self.entity_description.native_max_value_key)
        if self.entity_description.native_max_value is not None:
            return self.entity_description.native_max_value
        return DEFAULT_MAX_VALUE

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await getattr(self.device, self.entity_description.setter_key)(value)
