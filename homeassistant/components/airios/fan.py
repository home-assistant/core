"""Fan platform for the Airios integration."""

from __future__ import annotations

import logging
from typing import Any, cast, final

from pyairios import VMD02RPS78, AiriosException, ProductId
from pyairios.constants import VMDRequestedVentilationSpeed, VMDVentilationSpeed
from pyairios.data_model import AiriosNodeData

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_SLAVE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AiriosDataUpdateCoordinator
from .entity import AiriosEntity
from .services import (
    SERVICE_SCHEMA_SET_PRESET_FAN_SPEED,
    SERVICE_SCHEMA_SET_PRESET_MODE_DURATION,
    SERVICE_SET_PRESET_FAN_SPEED_AWAY,
    SERVICE_SET_PRESET_FAN_SPEED_HIGH,
    SERVICE_SET_PRESET_FAN_SPEED_LOW,
    SERVICE_SET_PRESET_FAN_SPEED_MEDIUM,
    SERVICE_SET_PRESET_MODE_DURATION,
)

_LOGGER = logging.getLogger(__name__)


PRESET_NAMES = {
    VMDVentilationSpeed.OFF: "off",
    VMDVentilationSpeed.LOW: "low",
    VMDVentilationSpeed.MID: "mid",
    VMDVentilationSpeed.HIGH: "high",
    VMDVentilationSpeed.OVERRIDE_LOW: "low_override",
    VMDVentilationSpeed.OVERRIDE_MID: "mid_override",
    VMDVentilationSpeed.OVERRIDE_HIGH: "high_override",
    VMDVentilationSpeed.AWAY: "away",
    VMDVentilationSpeed.BOOST: "boost",
    VMDVentilationSpeed.AUTO: "auto",
}

PRESET_VALUES = {value: key for (key, value) in PRESET_NAMES.items()}

PRESET_TO_VMD_SPEED = {
    "off": VMDRequestedVentilationSpeed.OFF,
    "low": VMDRequestedVentilationSpeed.LOW,
    "mid": VMDRequestedVentilationSpeed.MID,
    "high": VMDRequestedVentilationSpeed.HIGH,
    "low_override": VMDRequestedVentilationSpeed.LOW,
    "mid_override": VMDRequestedVentilationSpeed.MID,
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
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number entities."""

    coordinator: AiriosDataUpdateCoordinator = entry.runtime_data

    for slave_id, node in coordinator.data.nodes.items():
        # Find matching subentry
        subentry_id = None
        subentry = None
        via = None
        for se_id, se in entry.subentries.items():
            if se.data[CONF_SLAVE] == slave_id:
                subentry_id = se_id
                subentry = se
                via = entry

        entities: list[FanEntity] = []

        result = node["product_id"]
        if result is None or result.value is None:
            raise ConfigEntryNotReady("Failed to fetch product id from node")
        product_id = result.value
        if product_id == ProductId.VMD_02RPS78:
            entities.extend(
                [
                    AiriosFanEntity(description, coordinator, node, via, subentry)
                    for description in VMD_FAN_ENTITIES
                ]
            )
        async_add_entities(entities, config_subentry_id=subentry_id)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_PRESET_FAN_SPEED_AWAY,
        SERVICE_SCHEMA_SET_PRESET_FAN_SPEED,
        "async_set_preset_fan_speed_away",
    )
    platform.async_register_entity_service(
        SERVICE_SET_PRESET_FAN_SPEED_LOW,
        SERVICE_SCHEMA_SET_PRESET_FAN_SPEED,
        "async_set_preset_fan_speed_low",
    )
    platform.async_register_entity_service(
        SERVICE_SET_PRESET_FAN_SPEED_MEDIUM,
        SERVICE_SCHEMA_SET_PRESET_FAN_SPEED,
        "async_set_preset_fan_speed_low",
    )
    platform.async_register_entity_service(
        SERVICE_SET_PRESET_FAN_SPEED_HIGH,
        SERVICE_SCHEMA_SET_PRESET_FAN_SPEED,
        "async_set_preset_fan_speed_low",
    )
    platform.async_register_entity_service(
        SERVICE_SET_PRESET_MODE_DURATION,
        SERVICE_SCHEMA_SET_PRESET_MODE_DURATION,
        "async_set_preset_mode_duration",
    )


class AiriosFanEntity(AiriosEntity, FanEntity):
    """Airios fan entity."""

    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_preset_modes = list(PRESET_NAMES.values())

    def __init__(
        self,
        description: FanEntityDescription,
        coordinator: AiriosDataUpdateCoordinator,
        node: AiriosNodeData,
        via_config_entry: ConfigEntry | None,
        subentry: ConfigSubentry | None,
    ) -> None:
        """Initialize the Airios fan entity."""

        super().__init__(description.key, coordinator, node, via_config_entry, subentry)
        self.entity_description = description

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
            node = cast(VMD02RPS78, await self.api().node(self.slave_id))
            vmd_speed = PRESET_TO_VMD_SPEED[preset_mode]

            # Handle temporary overrides
            if preset_mode in (
                PRESET_NAMES[VMDVentilationSpeed.OVERRIDE_LOW],
                PRESET_NAMES[VMDVentilationSpeed.OVERRIDE_MID],
                PRESET_NAMES[VMDVentilationSpeed.OVERRIDE_HIGH],
            ):
                ret = await node.set_ventilation_speed_override_time(vmd_speed, 60)
            else:
                ret = await node.set_ventilation_speed(vmd_speed)
        except AiriosException as ex:
            raise HomeAssistantError(f"Failed to set preset {preset_mode}") from ex
        else:
            return ret

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
            device = self.coordinator.data.nodes[self.slave_id]
            result = device[self.entity_description.key]
            _LOGGER.debug(
                "Node %s, fan %s, result %s",
                f"0x{self.rf_address:08X}",
                self.entity_description.key,
                result,
            )
            if result is not None and result.value is not None:
                self._attr_preset_mode = PRESET_NAMES[result.value]
                self._attr_available = self._attr_preset_mode is not None
                if result.status is not None:
                    self.set_extra_state_attributes_internal(result.status)
        except (TypeError, ValueError) as ex:
            _LOGGER.error(
                "Failed to update node %s fan %s: %s",
                f"0x{self.rf_address:08X}",
                self.entity_description.key,
                ex,
            )
            self._attr_available = False
        finally:
            self.async_write_ha_state()

    @final
    async def async_set_preset_fan_speed_away(
        self,
        supply_fan_speed: int,
        exhaust_fan_speed: int,
    ) -> bool:
        """Set the fans speeds for the away preset mode."""
        node = cast(VMD02RPS78, await self.api().node(self.slave_id))
        _LOGGER.info(
            "Setting fans speeds for away preset on node %s to: supply=%d%%, exhaust=%d%%",
            str(node),
            supply_fan_speed,
            exhaust_fan_speed,
        )
        try:
            if not await node.set_preset_standby_fan_speed_supply(supply_fan_speed):
                raise HomeAssistantError(
                    f"Failed to set supply fan speed to {supply_fan_speed}"
                )
            if not await node.set_preset_standby_fan_speed_exhaust(exhaust_fan_speed):
                raise HomeAssistantError(
                    f"Failed to set exhaust fan speed to {supply_fan_speed}"
                )
        except AiriosException as ex:
            raise HomeAssistantError(f"Failed to set fan speeds: {ex}") from ex
        return True

    @final
    async def async_set_preset_fan_speed_low(
        self,
        supply_fan_speed: int,
        exhaust_fan_speed: int,
    ) -> bool:
        """Set the fans speeds for the low preset mode."""
        node = cast(VMD02RPS78, await self.api().node(self.slave_id))
        _LOGGER.info(
            "Setting fans speeds for low preset on node %s to: supply=%d%%, exhaust=%d%%",
            str(node),
            supply_fan_speed,
            exhaust_fan_speed,
        )
        try:
            if not await node.set_preset_low_fan_speed_supply(supply_fan_speed):
                raise HomeAssistantError(
                    f"Failed to set supply fan speed to {supply_fan_speed}"
                )
            if not await node.set_preset_low_fan_speed_exhaust(exhaust_fan_speed):
                raise HomeAssistantError(
                    f"Failed to set exhaust fan speed to {supply_fan_speed}"
                )
        except AiriosException as ex:
            raise HomeAssistantError(f"Failed to set fan speeds: {ex}") from ex
        return True

    @final
    async def async_set_preset_fan_speed_medium(
        self,
        supply_fan_speed: int,
        exhaust_fan_speed: int,
    ) -> bool:
        """Set the fans speeds for the medium preset mode."""
        node = cast(VMD02RPS78, await self.api().node(self.slave_id))
        _LOGGER.info(
            "Setting fans speeds for medium preset on node %s to: supply=%d%%, exhaust=%d%%",
            str(node),
            supply_fan_speed,
            exhaust_fan_speed,
        )
        try:
            if not await node.set_preset_medium_fan_speed_supply(supply_fan_speed):
                raise HomeAssistantError(
                    f"Failed to set supply fan speed to {supply_fan_speed}"
                )
            if not await node.set_preset_medium_fan_speed_exhaust(exhaust_fan_speed):
                raise HomeAssistantError(
                    f"Failed to set exhaust fan speed to {supply_fan_speed}"
                )
        except AiriosException as ex:
            raise HomeAssistantError(f"Failed to set fan speeds: {ex}") from ex
        return True

    @final
    async def async_set_preset_fan_speed_high(
        self,
        supply_fan_speed: int,
        exhaust_fan_speed: int,
    ) -> bool:
        """Set the fans speeds for the high preset mode."""
        node = cast(VMD02RPS78, await self.api().node(self.slave_id))
        _LOGGER.info(
            "Setting fans speeds for high preset on node %s to: supply=%d%%, exhaust=%d%%",
            str(node),
            supply_fan_speed,
            exhaust_fan_speed,
        )
        try:
            if not await node.set_preset_high_fan_speed_supply(supply_fan_speed):
                raise HomeAssistantError(
                    f"Failed to set supply fan speed to {supply_fan_speed}"
                )
            if not await node.set_preset_high_fan_speed_exhaust(exhaust_fan_speed):
                raise HomeAssistantError(
                    f"Failed to set exhaust fan speed to {supply_fan_speed}"
                )
        except AiriosException as ex:
            raise HomeAssistantError(f"Failed to set fan speeds: {ex}") from ex
        return True

    @final
    async def async_set_preset_mode_duration(
        self, preset_mode: str, preset_override_time: int
    ):
        """Set the preset mode for a limited time."""
        if preset_mode == PRESET_NAMES[VMDVentilationSpeed.LOW]:
            preset_mode = "low_override"
        elif preset_mode == PRESET_NAMES[VMDVentilationSpeed.MID]:
            preset_mode = "mid_override"
        elif preset_mode == PRESET_NAMES[VMDVentilationSpeed.HIGH]:
            preset_mode = "high_override"
        else:
            raise HomeAssistantError(
                f"Temporary override not available for preset [{preset_mode}]"
            )
        vmd_speed = PRESET_TO_VMD_SPEED[preset_mode]
        node = cast(VMD02RPS78, await self.api().node(self.slave_id))
        _LOGGER.info(
            "Setting preset mode on node %s to: %s for %s minutes",
            str(node),
            vmd_speed,
            preset_override_time,
        )
        return await node.set_ventilation_speed_override_time(
            vmd_speed, preset_override_time
        )
