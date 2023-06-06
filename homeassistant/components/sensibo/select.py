"""Select platform for Sensibo integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pysensibo.model import SensiboDevice

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, async_handle_api_call

PARALLEL_UPDATES = 0


@dataclass
class SensiboSelectDescriptionMixin:
    """Mixin values for Sensibo entities."""

    data_key: str
    value_fn: Callable[[SensiboDevice], str | None]
    options_fn: Callable[[SensiboDevice], list[str] | None]
    transformation: Callable[[SensiboDevice], dict | None]


@dataclass
class SensiboSelectEntityDescription(
    SelectEntityDescription, SensiboSelectDescriptionMixin
):
    """Class describing Sensibo Select entities."""


DEVICE_SELECT_TYPES = (
    SensiboSelectEntityDescription(
        key="horizontalSwing",
        data_key="horizontal_swing_mode",
        name="Horizontal swing",
        icon="mdi:air-conditioner",
        value_fn=lambda data: data.horizontal_swing_mode,
        options_fn=lambda data: data.horizontal_swing_modes,
        translation_key="horizontalswing",
        transformation=lambda data: data.horizontal_swing_modes_translated,
    ),
    SensiboSelectEntityDescription(
        key="light",
        data_key="light_mode",
        name="Light",
        icon="mdi:flashlight",
        value_fn=lambda data: data.light_mode,
        options_fn=lambda data: data.light_modes,
        translation_key="light",
        transformation=lambda data: data.light_modes_translated,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo number platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SensiboSelect(coordinator, device_id, description)
        for device_id, device_data in coordinator.data.parsed.items()
        for description in DEVICE_SELECT_TYPES
        if description.key in device_data.full_features
    )


class SensiboSelect(SensiboDeviceBaseEntity, SelectEntity):
    """Representation of a Sensibo Select."""

    entity_description: SensiboSelectEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: SensiboSelectEntityDescription,
    ) -> None:
        """Initiate Sensibo Select."""
        super().__init__(coordinator, device_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self.entity_description.value_fn(self.device_data)

    @property
    def options(self) -> list[str]:
        """Return possible options."""
        options = self.entity_description.options_fn(self.device_data)
        if TYPE_CHECKING:
            assert options is not None
        return options

    async def async_select_option(self, option: str) -> None:
        """Set state to the selected option."""
        if self.entity_description.key not in self.device_data.active_features:
            raise HomeAssistantError(
                f"Current mode {self.device_data.hvac_mode} doesn't support setting"
                f" {self.entity_description.name}"
            )

        await self.async_send_api_call(
            key=self.entity_description.data_key,
            value=option,
        )

    @async_handle_api_call
    async def async_send_api_call(self, key: str, value: Any) -> bool:
        """Make service call to api."""
        transformation = self.entity_description.transformation(self.device_data)
        if TYPE_CHECKING:
            assert transformation is not None

        data = {
            "name": self.entity_description.key,
            "value": value,
            "ac_states": self.device_data.ac_states,
            "assumed_state": False,
        }
        result = await self._client.async_set_ac_state_property(
            self._device_id,
            data["name"],
            transformation[data["value"]],
            data["ac_states"],
            data["assumed_state"],
        )
        return bool(result.get("result", {}).get("status") == "Success")
