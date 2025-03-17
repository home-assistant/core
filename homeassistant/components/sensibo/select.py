"""Select platform for Sensibo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pysensibo.model import SensiboDevice

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

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


HORIZONTAL_SWING_MODE_TYPE = SensiboSelectEntityDescription(
    key="horizontalSwing",
    data_key="horizontal_swing_mode",
    value_fn=lambda data: data.horizontal_swing_mode,
    options_fn=lambda data: data.horizontal_swing_modes,
    translation_key="horizontalswing",
    transformation=lambda data: data.horizontal_swing_modes_translated,
    entity_registry_enabled_default=False,
)

DEVICE_SELECT_TYPES = (
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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sensibo select platform."""

    coordinator = entry.runtime_data

    entities: list[SensiboSelect] = []

    entity_registry = er.async_get(hass)
    for device_id, device_data in coordinator.data.parsed.items():
        if entity_id := entity_registry.async_get_entity_id(
            SELECT_DOMAIN, DOMAIN, f"{device_id}-horizontalSwing"
        ):
            entity = entity_registry.async_get(entity_id)
            if entity and entity.disabled:
                entity_registry.async_remove(entity_id)
                async_delete_issue(
                    hass,
                    DOMAIN,
                    "deprecated_entity_horizontalswing",
                )
            elif entity and HORIZONTAL_SWING_MODE_TYPE.key in device_data.full_features:
                entities.append(
                    SensiboSelect(coordinator, device_id, HORIZONTAL_SWING_MODE_TYPE)
                )
                if automations_with_entity(hass, entity_id) or scripts_with_entity(
                    hass, entity_id
                ):
                    async_create_issue(
                        hass,
                        DOMAIN,
                        "deprecated_entity_horizontalswing",
                        breaks_in_ha_version="2025.8.0",
                        is_fixable=False,
                        severity=IssueSeverity.WARNING,
                        translation_key="deprecated_entity_horizontalswing",
                        translation_placeholders={
                            "name": str(entity.name or entity.original_name),
                            "entity": entity_id,
                        },
                    )
    async_add_entities(entities)

    added_devices: set[str] = set()

    def _add_remove_devices() -> None:
        """Handle additions of devices and sensors."""
        nonlocal added_devices
        new_devices, _, new_added_devices = coordinator.get_devices(added_devices)
        added_devices = new_added_devices

        if new_devices:
            async_add_entities(
                SensiboSelect(coordinator, device_id, description)
                for device_id, device_data in coordinator.data.parsed.items()
                if device_id in new_devices
                for description in DEVICE_SELECT_TYPES
                if description.key in device_data.full_features
            )

    entry.async_on_unload(coordinator.async_add_listener(_add_remove_devices))
    _add_remove_devices()


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
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.entity_description.key not in self.device_data.active_features:
            return False
        return super().available

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
