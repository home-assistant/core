"""Support for KNX/IP climate devices."""
from __future__ import annotations

from typing import Any

from xknx.devices import Climate as XknxClimate
from xknx.dpt.dpt_hvac_mode import HVACControllerMode, HVACOperationMode
from xknx.telegram.address import parse_device_group_address

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONTROLLER_MODES, DOMAIN, PRESET_MODES
from .knx_entity import KnxEntity
from .schema import ClimateSchema

CONTROLLER_MODES_INV = {value: key for key, value in CONTROLLER_MODES.items()}
PRESET_MODES_INV = {value: key for key, value in PRESET_MODES.items()}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up climate(s) for KNX platform."""
    _async_migrate_unique_id(hass, discovery_info)
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxClimate):
            entities.append(KNXClimate(device))
    async_add_entities(entities)


@callback
def _async_migrate_unique_id(
    hass: HomeAssistant, discovery_info: DiscoveryInfoType | None
) -> None:
    """Change unique_ids used in 2021.4 to include target_temperature GA."""
    entity_registry = er.async_get(hass)
    if not discovery_info or not discovery_info["platform_config"]:
        return

    platform_config = discovery_info["platform_config"]
    for entity_config in platform_config:
        # normalize group address strings - ga_temperature_state was the old uid
        ga_temperature_state = parse_device_group_address(
            entity_config[ClimateSchema.CONF_TEMPERATURE_ADDRESS][0]
        )
        old_uid = str(ga_temperature_state)

        entity_id = entity_registry.async_get_entity_id("climate", DOMAIN, old_uid)
        if entity_id is None:
            continue
        ga_target_temperature_state = parse_device_group_address(
            entity_config[ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS][0]
        )
        new_uid = f"{ga_temperature_state}_{ga_target_temperature_state}"
        entity_registry.async_update_entity(entity_id, new_unique_id=new_uid)


class KNXClimate(KnxEntity, ClimateEntity):
    """Representation of a KNX climate device."""

    def __init__(self, device: XknxClimate) -> None:
        """Initialize of a KNX climate device."""
        self._device: XknxClimate
        super().__init__(device)
        self._unique_id = (
            f"{device.temperature.group_address_state}_"
            f"{device.target_temperature.group_address_state}"
        )
        self._unit_of_measurement = TEMP_CELSIUS

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    async def async_update(self) -> None:
        """Request a state update from KNX bus."""
        await self._device.sync()
        if self._device.mode is not None:
            await self._device.mode.sync()

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.temperature.value

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return self._device.temperature_step

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.target_temperature.value

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        temp = self._device.target_temperature_min
        return temp if temp is not None else super().min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        temp = self._device.target_temperature_max
        return temp if temp is not None else super().max_temp

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._device.set_target_temperature(temperature)
        self.async_write_ha_state()

    @property
    def hvac_mode(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        if self._device.supports_on_off and not self._device.is_on:
            return HVAC_MODE_OFF
        if self._device.mode is not None and self._device.mode.supports_controller_mode:
            return CONTROLLER_MODES.get(
                self._device.mode.controller_mode.value, HVAC_MODE_HEAT
            )
        # default to "heat"
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available operation/controller modes."""
        ha_controller_modes: list[str | None] = []
        if self._device.mode is not None:
            for knx_controller_mode in self._device.mode.controller_modes:
                ha_controller_modes.append(
                    CONTROLLER_MODES.get(knx_controller_mode.value)
                )

        if self._device.supports_on_off:
            if not ha_controller_modes:
                ha_controller_modes.append(HVAC_MODE_HEAT)
            ha_controller_modes.append(HVAC_MODE_OFF)

        hvac_modes = list(set(filter(None, ha_controller_modes)))
        # default to ["heat"]
        return hvac_modes if hvac_modes else [HVAC_MODE_HEAT]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set operation mode."""
        if self._device.supports_on_off and hvac_mode == HVAC_MODE_OFF:
            await self._device.turn_off()
        else:
            if self._device.supports_on_off and not self._device.is_on:
                await self._device.turn_on()
            if (
                self._device.mode is not None
                and self._device.mode.supports_controller_mode
            ):
                knx_controller_mode = HVACControllerMode(
                    CONTROLLER_MODES_INV.get(hvac_mode)
                )
                await self._device.mode.set_controller_mode(knx_controller_mode)
        self.async_write_ha_state()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        if self._device.mode is not None and self._device.mode.supports_operation_mode:
            return PRESET_MODES.get(self._device.mode.operation_mode.value, PRESET_AWAY)
        return None

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        if self._device.mode is None:
            return None

        presets = [
            PRESET_MODES.get(operation_mode.value)
            for operation_mode in self._device.mode.operation_modes
        ]
        return list(filter(None, presets))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self._device.mode is not None and self._device.mode.supports_operation_mode:
            knx_operation_mode = HVACOperationMode(PRESET_MODES_INV.get(preset_mode))
            await self._device.mode.set_operation_mode(knx_operation_mode)
            self.async_write_ha_state()
