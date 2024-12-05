"""Module for Growatt switch integration with Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GrowattCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class GrowattRequiredNumberKey:
    """Mixin for required keys."""

    api_key: str


@dataclass(frozen=True)
class GrowattSwitchEntityDescription(SwitchEntityDescription, GrowattRequiredNumberKey):
    """Describes Growatt number entity."""


TLX_SWITCH_TYPES: tuple[GrowattSwitchEntityDescription, ...] = (
    GrowattSwitchEntityDescription(
        api_key="ac_charge",
        key="tlx_ac_charge",
        translation_key="tlx_ac_charge",
    ),
)


class GrowattSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Growatt switch."""

    _attr_has_entity_name = True
    coordinator: GrowattCoordinator
    entity_description: GrowattSwitchEntityDescription

    def __init__(
        self,
        coordinator: GrowattCoordinator,
        device_name: str,
        serial_id: str,
        unique_id: str,
        description: GrowattSwitchEntityDescription,
    ) -> None:
        """Initialize a Growatt switch."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:solar-power"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_id)}, manufacturer="Growatt", name=device_name
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.get_value(self.entity_description) == "1"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        res = await self.hass.async_add_executor_job(
            self.coordinator.api.update_tlx_inverter_setting,
            self.coordinator.device_id,
            self.entity_description.api_key,
            "1",
        )
        _LOGGER.debug(
            "Turn the switch on: %s, res: %s", self.entity_description.key, res
        )
        if res.get("success"):
            # If success, update single parameter value in coordinator instead of
            # fetching all data with coordinator.async_refresh() to off-load the API
            self.coordinator.set_value(self.entity_description, "1")
            self.async_write_ha_state()
        else:
            _LOGGER.error(
                "Turn on switch %d failed, msg: %s, error: %s",
                self.entity_description.key,
                res.get("msg"),
                res.get("error"),
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        res = await self.hass.async_add_executor_job(
            self.coordinator.api.update_tlx_inverter_setting,
            self.coordinator.device_id,
            self.entity_description.api_key,
            "0",
        )
        _LOGGER.debug(
            "Turn the switch off: %s, res: %s", self.entity_description.key, res
        )
        if res.get("success"):
            # If success, update single parameter value in coordinator instead of
            # fetching all data with coordinator.async_refresh() to off-load the API
            self.coordinator.set_value(self.entity_description, "0")
            self.async_write_ha_state()
        else:
            _LOGGER.error(
                "Turn off switch %d failed, msg: %s, error: %s",
                self.entity_description.key,
                res.get("msg"),
                res.get("error"),
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Growatt switch."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Add switches for each device type
    for device_sn, device_coordinator in coordinators["devices"].items():
        if device_coordinator.device_type == "tlx":
            for description in TLX_SWITCH_TYPES:
                entities.extend(
                    [
                        GrowattSwitch(
                            device_coordinator,
                            device_name=device_sn,
                            serial_id=device_sn,
                            unique_id=f"{device_sn}-{description.key}",
                            description=description,
                        )
                    ]
                )

        else:
            _LOGGER.debug(
                "Device type %s was found but is not supported right now",
                device_coordinator.device_type,
            )

    async_add_entities(entities, True)
