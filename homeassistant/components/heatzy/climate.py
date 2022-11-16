"""Climate sensors for Heatzy."""
from __future__ import annotations

import logging
from typing import Any

from heatzypy.exception import HeatzyException

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HeatzyDataUpdateCoordinator
from .const import (
    CFT_TEMP_H,
    CFT_TEMP_L,
    CONF_ALIAS,
    CONF_ATTR,
    CONF_ATTRS,
    CONF_MODE,
    CONF_MODEL,
    CONF_ON_OFF,
    CONF_PRODUCT_KEY,
    CONF_VERSION,
    CUR_TEMP_H,
    CUR_TEMP_L,
    DOMAIN,
    ECO_TEMP_H,
    ECO_TEMP_L,
    ELEC_PRO_SOC,
    PILOTE_V1,
    PILOTE_V2,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Load all Heatzy devices."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[HeatzyThermostat] = []
    for unique_id, device in coordinator.data.items():
        product_key = device.get(CONF_PRODUCT_KEY)
        if product_key in PILOTE_V1:
            entities.append(HeatzyPiloteV1Thermostat(coordinator, unique_id))
        elif product_key in PILOTE_V2 or product_key in ELEC_PRO_SOC:
            entities.append(HeatzyPiloteV2Thermostat(coordinator, unique_id))
        else:
            entities.append(Glowv1Thermostat(coordinator, unique_id))
    async_add_entities(entities)


class HeatzyThermostat(CoordinatorEntity[HeatzyDataUpdateCoordinator], ClimateEntity):
    """Heatzy climate."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [PRESET_NONE, PRESET_COMFORT, PRESET_ECO, PRESET_AWAY]
    _attr_supported_features = ClimateEntityFeature.PRESET_MODE
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HeatzyDataUpdateCoordinator, unique_id: str
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_name = coordinator.data[unique_id][CONF_ALIAS]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=coordinator.data[unique_id][CONF_ALIAS],
            manufacturer=DOMAIN,
            sw_version=coordinator.data[unique_id].get(CONF_VERSION),
            model=coordinator.data[unique_id].get(CONF_MODEL),
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if self.preset_mode == PRESET_NONE:
            return HVACMode.OFF
        return HVACMode.HEAT

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        """Turn device on."""
        await self.async_set_preset_mode(PRESET_COMFORT)

    async def async_turn_off(self) -> None:
        """Turn device off."""
        await self.async_set_preset_mode(PRESET_NONE)


class HeatzyPiloteV1Thermostat(HeatzyThermostat):
    """Heaty Pilote v1."""

    HEATZY_TO_HA_STATE = {
        "\u8212\u9002": PRESET_COMFORT,
        "\u7ecf\u6d4e": PRESET_ECO,
        "\u89e3\u51bb": PRESET_AWAY,
        "\u505c\u6b62": PRESET_NONE,
    }
    HA_TO_HEATZY_STATE = {
        PRESET_COMFORT: [1, 1, 0],
        PRESET_ECO: [1, 1, 1],
        PRESET_AWAY: [1, 1, 2],
        PRESET_NONE: [1, 1, 3],
    }

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return self.HEATZY_TO_HA_STATE.get(
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CONF_MODE)
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        try:
            await self.coordinator.api.async_control_device(
                self.unique_id,
                {"raw": self.HA_TO_HEATZY_STATE.get(preset_mode)},
            )
            await self.coordinator.async_request_refresh()
        except HeatzyException as error:
            _LOGGER.error(
                "Set preset mode (%s) %s (%s)",
                preset_mode,
                error,
                self.name,
                exc_info=True,
            )


class HeatzyPiloteV2Thermostat(HeatzyThermostat):
    """Heaty Pilote v2."""

    HEATZY_TO_HA_STATE = {
        "cft": PRESET_COMFORT,
        "eco": PRESET_ECO,
        "fro": PRESET_AWAY,
        "stop": PRESET_NONE,
    }

    HA_TO_HEATZY_STATE = {
        PRESET_COMFORT: "cft",
        PRESET_ECO: "eco",
        PRESET_AWAY: "fro",
        PRESET_NONE: "stop",
    }

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return self.HEATZY_TO_HA_STATE.get(
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CONF_MODE)
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        try:
            await self.coordinator.api.async_control_device(
                self.unique_id,
                {CONF_ATTRS: {CONF_MODE: self.HA_TO_HEATZY_STATE.get(preset_mode)}},
            )
            await self.coordinator.async_request_refresh()
        except HeatzyException as error:
            _LOGGER.error(
                "Set preset mode (%s) %s (%s)",
                preset_mode,
                error,
                self.name,
                exc_info=True,
            )


class Glowv1Thermostat(HeatzyPiloteV2Thermostat):
    """Heatzy Glow."""

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.PRESET_MODE
        )

    @property
    def current_temperature(self) -> float:
        """Return current temperature."""
        cur_temp_high = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CUR_TEMP_H, 0)
        )
        cur_temp_low = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CUR_TEMP_L, 0)
        )
        return (cur_temp_low + (cur_temp_high * 255)) / 10

    @property
    def target_temperature_high(self) -> float:
        """Return comfort temperature."""
        cft_temp_high = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CFT_TEMP_H, 0)
        )
        cft_temp_low = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CFT_TEMP_L, 0)
        )
        return (cft_temp_low + (cft_temp_high * 255)) / 10

    @property
    def target_temperature_low(self) -> float:
        """Return comfort temperature."""
        eco_temp_high = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(ECO_TEMP_H, 0)
        )
        eco_temp_low = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(ECO_TEMP_L, 0)
        )
        return (eco_temp_low + (eco_temp_high * 255)) / 10

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp_eco = kwargs[ATTR_TARGET_TEMP_LOW]
        temp_cft = kwargs[ATTR_TARGET_TEMP_HIGH]

        if (temp_eco or temp_cft) is None:
            return

        b_temp_cft = int(temp_cft * 10)
        b_temp_eco = int(temp_eco * 10)

        self.coordinator.data[self.unique_id].get(CONF_ATTR, {})[
            ECO_TEMP_L
        ] = b_temp_eco
        self.coordinator.data[self.unique_id].get(CONF_ATTR, {})[
            CFT_TEMP_L
        ] = b_temp_cft

        try:
            await self.coordinator.api.async_control_device(
                self.unique_id,
                {
                    CONF_ATTRS: {
                        CFT_TEMP_L: b_temp_cft,
                        ECO_TEMP_L: b_temp_eco,
                    }
                },
            )
            await self.coordinator.async_request_refresh()
        except HeatzyException as error:
            _LOGGER.error(
                "Error to set temperature: %s",
                error,
                exc_info=True,
            )

    async def async_turn_on(self) -> None:
        """Turn device on."""
        try:
            await self.coordinator.api.async_control_device(
                self.unique_id, {CONF_ATTRS: {CONF_ON_OFF: 1}}
            )
            await self.coordinator.async_request_refresh()
        except HeatzyException as error:
            _LOGGER.error(
                "Error to turn on : %s",
                error,
                exc_info=True,
            )

    async def async_turn_off(self) -> None:
        """Turn device off."""
        try:
            await self.coordinator.api.async_control_device(
                self.unique_id, {CONF_ATTRS: {CONF_ON_OFF: 0}}
            )
            await self.coordinator.async_request_refresh()
        except HeatzyException as error:
            _LOGGER.error(
                "Error to turn off : %s",
                error,
                exc_info=True,
            )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CONF_ON_OFF)
            == 0
        ):
            return HVACMode.OFF
        return HVACMode.HEAT
