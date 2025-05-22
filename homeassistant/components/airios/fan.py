"""Fan platform for the Airios integration."""

from __future__ import annotations

import logging
from typing import Any, cast

from pyairios import VMD02RPS78, AiriosException, ProductId
from pyairios.constants import (
    VMDCapabilities,
    VMDRequestedVentilationSpeed,
    VMDVentilationSpeed,
)
from pyairios.data_model import AiriosNodeData

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AiriosConfigEntry
from .coordinator import AiriosDataUpdateCoordinator
from .entity import AiriosEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

PRESET_NAMES = {
    VMDVentilationSpeed.OFF: "off",
    VMDVentilationSpeed.LOW: "low",
    VMDVentilationSpeed.MID: "medium",
    VMDVentilationSpeed.HIGH: "high",
    VMDVentilationSpeed.OVERRIDE_LOW: "low_override",
    VMDVentilationSpeed.OVERRIDE_MID: "medium_override",
    VMDVentilationSpeed.OVERRIDE_HIGH: "high_override",
    VMDVentilationSpeed.AWAY: "away",
    VMDVentilationSpeed.BOOST: "boost",
    VMDVentilationSpeed.AUTO: "auto",
}

PRESET_VALUES = {value: key for (key, value) in PRESET_NAMES.items()}

PRESET_TO_VMD_SPEED = {
    "off": VMDRequestedVentilationSpeed.OFF,
    "low": VMDRequestedVentilationSpeed.LOW,
    "medium": VMDRequestedVentilationSpeed.MID,
    "high": VMDRequestedVentilationSpeed.HIGH,
    "low_override": VMDRequestedVentilationSpeed.LOW,
    "medium_override": VMDRequestedVentilationSpeed.MID,
    "high_override": VMDRequestedVentilationSpeed.HIGH,
    "away": VMDRequestedVentilationSpeed.AWAY,
    "boost": VMDRequestedVentilationSpeed.BOOST,
    "auto": VMDRequestedVentilationSpeed.AUTO,
}


VMD_FAN_ENTITIES: tuple[FanEntityDescription, ...] = (
    FanEntityDescription(
        key="ventilation_speed",
        translation_key="ventilation_speed",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AiriosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number entities."""

    coordinator: AiriosDataUpdateCoordinator = entry.runtime_data

    for modbus_address, node in coordinator.data.nodes.items():
        # Find matching subentry
        subentry_id = None
        subentry = None
        via = None
        for se_id, se in entry.subentries.items():
            if se.data[CONF_ADDRESS] == modbus_address:
                subentry_id = se_id
                subentry = se
                via = entry

        entities: list[FanEntity] = []

        result = node["product_id"]
        if result is None or result.value is None:
            raise PlatformNotReady("Failed to fetch product id from node")
        product_id = result.value

        try:
            if product_id == ProductId.VMD_02RPS78:
                vmd = cast(VMD02RPS78, await coordinator.api.node(modbus_address))
                result = await vmd.capabilities()
                capabilities = result.value
                entities.extend(
                    [
                        AiriosFanEntity(
                            description, coordinator, node, capabilities, via, subentry
                        )
                        for description in VMD_FAN_ENTITIES
                    ]
                )
            async_add_entities(entities, config_subentry_id=subentry_id)
        except AiriosException as ex:
            _LOGGER.warning("Failed to setup platform: %s", ex)
            raise PlatformNotReady from ex


class AiriosFanEntity(AiriosEntity, FanEntity):
    """Airios fan entity."""

    _attr_name = None
    _attr_supported_features = FanEntityFeature.PRESET_MODE
    _attr_preset_modes: list[str] | None = [
        PRESET_NAMES[VMDVentilationSpeed.LOW],
        PRESET_NAMES[VMDVentilationSpeed.MID],
        PRESET_NAMES[VMDVentilationSpeed.HIGH],
    ]

    def __init__(
        self,
        description: FanEntityDescription,
        coordinator: AiriosDataUpdateCoordinator,
        node: AiriosNodeData,
        capabilities: VMDCapabilities,
        via_config_entry: ConfigEntry | None,
        subentry: ConfigSubentry | None,
    ) -> None:
        """Initialize the Airios fan entity."""

        super().__init__(description.key, coordinator, node, via_config_entry, subentry)
        self.entity_description = description

        _LOGGER.info(
            "Fan for node %s@%s capable of %s",
            node["product_name"],
            node["slave_id"],
            capabilities,
        )

        assert self._attr_preset_modes is not None
        if VMDCapabilities.AUTO_MODE_CAPABLE in capabilities:
            self._attr_preset_modes.append(PRESET_NAMES[VMDVentilationSpeed.AUTO])
        if VMDCapabilities.AWAY_MODE_CAPABLE in capabilities:
            self._attr_preset_modes.append(PRESET_NAMES[VMDVentilationSpeed.AWAY])
        if VMDCapabilities.BOOST_MODE_CAPABLE in capabilities:
            self._attr_preset_modes.append(PRESET_NAMES[VMDVentilationSpeed.BOOST])
        if VMDCapabilities.TIMER_CAPABLE in capabilities:
            self._attr_preset_modes.append(
                PRESET_NAMES[VMDVentilationSpeed.OVERRIDE_LOW]
            )
            self._attr_preset_modes.append(
                PRESET_NAMES[VMDVentilationSpeed.OVERRIDE_MID]
            )
            self._attr_preset_modes.append(
                PRESET_NAMES[VMDVentilationSpeed.OVERRIDE_HIGH]
            )

        if VMDCapabilities.OFF_CAPABLE in capabilities:
            self._attr_supported_features |= FanEntityFeature.TURN_OFF
            self._attr_supported_features |= FanEntityFeature.TURN_ON

    async def _turn_on_internal(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
    ) -> bool:
        if self.is_on:
            return False
        if preset_mode is None:
            preset_mode = PRESET_NAMES[VMDVentilationSpeed.MID]
        return await self._set_preset_mode_internal(preset_mode)

    async def _turn_off_internal(self) -> bool:
        if not self.is_on:
            return False
        return await self._set_preset_mode_internal(
            PRESET_NAMES[VMDVentilationSpeed.OFF]
        )

    async def _set_preset_mode_internal(self, preset_mode: str) -> bool:
        if preset_mode == self.preset_mode:
            return False

        try:
            node = cast(VMD02RPS78, await self.api().node(self.modbus_address))
            vmd_speed = PRESET_TO_VMD_SPEED[preset_mode]

            # Handle temporary overrides
            if preset_mode in (
                PRESET_NAMES[VMDVentilationSpeed.OVERRIDE_LOW],
                PRESET_NAMES[VMDVentilationSpeed.OVERRIDE_MID],
                PRESET_NAMES[VMDVentilationSpeed.OVERRIDE_HIGH],
            ):
                return await node.set_ventilation_speed_override_time(vmd_speed, 60)
            return await node.set_ventilation_speed(vmd_speed)
        except AiriosException as ex:
            raise HomeAssistantError(f"Failed to set preset {preset_mode}") from ex

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        return (
            self.preset_mode is not None
            and self.preset_mode != PRESET_NAMES[VMDVentilationSpeed.OFF]
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        update_needed = await self._turn_on_internal(percentage, preset_mode)
        if update_needed:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        update_needed = await self._turn_off_internal()
        if update_needed:
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        update_needed = await self._set_preset_mode_internal(preset_mode)
        if update_needed:
            await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update data from the coordinator."""
        _LOGGER.debug(
            "Handle update for node %s fan %s",
            f"{self.rf_address}",
            self.entity_description.key,
        )
        try:
            device = self.coordinator.data.nodes[self.modbus_address]
            result = device[self.entity_description.key]
            _LOGGER.debug(
                "Node %s, fan %s, result %s",
                f"0x{self.rf_address:08X}",
                self.entity_description.key,
                result,
            )
            if result is not None and result.value is not None:
                self._attr_preset_mode = PRESET_NAMES[result.value]
            if result is not None and result.status is not None:
                self.set_extra_state_attributes_internal(result.status)
            self._attr_available = self._attr_preset_mode is not None
        except (TypeError, ValueError) as ex:
            _LOGGER.error(
                "Failed to update node %s fan %s: %s",
                f"0x{self.rf_address:08X}",
                self.entity_description.key,
                ex,
            )
            self._attr_available = False
        finally:
            if self._attr_available:
                self._unavailable_logged = False
            elif not self._unavailable_logged:
                _LOGGER.info(
                    "Node %s fan %s is unavailable",
                    f"0x{self.rf_address:08X}",
                    self.entity_description.key,
                )
                self._unavailable_logged = True
            self.async_write_ha_state()
