"""Select platform for Sensibo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pysensibo.model import SensiboDevice

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SensiboConfigEntry
from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, async_handle_api_call

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SensiboSelectEntityDescription(SelectEntityDescription):
    """Class describing Sensibo Select entities."""

    data_key: str
    value_fn: Callable[[SensiboDevice], str | None]
    options_fn: Callable[[SensiboDevice], list[str] | None]
    transformation: Callable[[SensiboDevice], dict | None]


DEVICE_SELECT_TYPES = (
    SensiboSelectEntityDescription(
        key="horizontalSwing",
        data_key="horizontal_swing_mode",
        value_fn=lambda data: data.horizontal_swing_mode,
        options_fn=lambda data: data.horizontal_swing_modes,
        translation_key="horizontalswing",
        transformation=lambda data: data.horizontal_swing_modes_translated,
        entity_registry_enabled_default=False,
    ),
    SensiboSelectEntityDescription(
        key="light",
        data_key="light_mode",
        value_fn=lambda data: data.light_mode,
        options_fn=lambda data: data.light_modes,
        translation_key="light",
        transformation=lambda data: data.light_modes_translated,
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
            hvac_mode = self.device_data.hvac_mode if self.device_data.hvac_mode else ""
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="select_option_not_available",
                translation_placeholders={
                    "hvac_mode": hvac_mode,
                    "key": self.entity_description.key,
                },
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
