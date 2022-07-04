"""Button platform for Sensibo integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pysensibo.model import SensiboDevice

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, api_call_decorator

PARALLEL_UPDATES = 0


@dataclass
class SensiboEntityDescriptionMixin:
    """Mixin values for Sensibo entities."""

    data_key: str


@dataclass
class SensiboButtonEntityDescription(
    ButtonEntityDescription, SensiboEntityDescriptionMixin
):
    """Class describing Sensibo Button entities."""


DEVICE_BUTTON_TYPES = SensiboButtonEntityDescription(
    key="reset_filter",
    name="Reset Filter",
    icon="mdi:air-filter",
    entity_category=EntityCategory.CONFIG,
    data_key="filter_clean",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo binary sensor platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensiboDeviceButton] = []

    entities.extend(
        SensiboDeviceButton(coordinator, device_id, DEVICE_BUTTON_TYPES)
        for device_id, device_data in coordinator.data.parsed.items()
    )

    async_add_entities(entities)


class SensiboDeviceButton(SensiboDeviceBaseEntity, ButtonEntity):
    """Representation of a Sensibo Device Binary Sensor."""

    entity_description: SensiboButtonEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: SensiboButtonEntityDescription,
    ) -> None:
        """Initiate Sensibo Device Button."""
        super().__init__(
            coordinator,
            device_id,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"
        self._attr_name = f"{self.device_data.name} {entity_description.name}"

    async def async_press(self) -> None:
        """Press the button."""
        await self.api_call(
            device_data=self.device_data,
            key=self.entity_description.data_key,
            value=False,
        )

    @api_call_decorator
    async def api_call(self, device_data: SensiboDevice, key: Any, value: Any) -> bool:
        """Make service call to api."""
        result = await self._client.async_reset_filter(
            self._device_id,
        )
        return bool(result.get("status") == "success")
