"""Support for Honeywell (US) Total Connect Comfort climate systems."""

from __future__ import annotations

import datetime
from typing import Any

from aiohttp import ClientConnectionError
from aiosomecomfort import (
    APIRateLimited,
    AuthError,
    ConnectionError as AscConnectionError,
    SomeComfortError,
    UnauthorizedError,
    UnexpectedResponse,
)
from aiosomecomfort.device import Device as SomeComfortDevice

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_ON,
    PRESET_AWAY,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HoneywellData
from .const import (
    _LOGGER,
    CONF_COOL_AWAY_TEMPERATURE,
    CONF_HEAT_AWAY_TEMPERATURE,
    DOMAIN,
    RETRY,
)

ATTR_FAN_ACTION = "fan_action"

ATTR_PERMANENT_HOLD = "permanent_hold"

PRESET_HOLD = "hold"

HEATING_MODES = {"heat", "emheat", "auto"}
COOLING_MODES = {"cool", "auto"}

HVAC_MODE_TO_HW_MODE = {
    "SwitchOffAllowed": {HVACMode.OFF: "off"},
    "SwitchAutoAllowed": {HVACMode.HEAT_COOL: "auto"},
    "SwitchCoolAllowed": {HVACMode.COOL: "cool"},
    "SwitchHeatAllowed": {HVACMode.HEAT: "heat"},
}
HW_MODE_TO_HVAC_MODE = {
    "off": HVACMode.OFF,
    "emheat": HVACMode.HEAT,
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "auto": HVACMode.HEAT_COOL,
}
HW_MODE_TO_HA_HVAC_ACTION = {
    "off": HVACAction.IDLE,
    "fan": HVACAction.FAN,
    "heat": HVACAction.HEATING,
    "cool": HVACAction.COOLING,
}
FAN_MODE_TO_HW = {
    "fanModeOnAllowed": {FAN_ON: "on"},
    "fanModeAutoAllowed": {FAN_AUTO: "auto"},
    "fanModeCirculateAllowed": {FAN_DIFFUSE: "circulate"},
}
HW_FAN_MODE_TO_HA = {
    "on": FAN_ON,
    "auto": FAN_AUTO,
    "circulate": FAN_DIFFUSE,
    "follow schedule": FAN_AUTO,
}

SCAN_INTERVAL = datetime.timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Honeywell thermostat."""
    cool_away_temp = entry.options.get(CONF_COOL_AWAY_TEMPERATURE)
    heat_away_temp = entry.options.get(CONF_HEAT_AWAY_TEMPERATURE)

    data: HoneywellData = hass.data[DOMAIN][entry.entry_id]
    _async_migrate_unique_id(hass, data.devices)
    async_add_entities(
        [
            HoneywellUSThermostat(data, device, cool_away_temp, heat_away_temp)
            for device in data.devices.values()
        ]
    )
    remove_stale_devices(hass, entry, data.devices)


def _async_migrate_unique_id(
    hass: HomeAssistant, devices: dict[str, SomeComfortDevice]
) -> None:
    """Migrate entities to string."""
    entity_registry = er.async_get(hass)
    for device in devices.values():
        entity_id = entity_registry.async_get_entity_id(
            "climate", DOMAIN, device.deviceid
        )
        if entity_id is not None:
            entity_registry.async_update_entity(
                entity_id, new_unique_id=str(device.deviceid)
            )


def remove_stale_devices(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    devices: dict[str, SomeComfortDevice],
) -> None:
    """Remove stale devices from device registry."""
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    all_device_ids = {device.deviceid for device in devices.values()}

    for device_entry in device_entries:
        device_id: str | None = None

        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                device_id = identifier[1]
                break

        if device_id is None or device_id not in all_device_ids:
            # If device_id is None an invalid device entry was found for this config entry.
            # If the device_id is not in existing device ids it's a stale device entry.
            # Remove config entry from this device entry in either case.
            device_registry.async_update_device(
                device_entry.id, remove_config_entry_id=config_entry.entry_id
            )


class HoneywellUSThermostat(ClimateEntity):
    """Representation of a Honeywell US Thermostat."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "honeywell"
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        data: HoneywellData,
        device: SomeComfortDevice,
        cool_away_temp: int | None,
        heat_away_temp: int | None,
    ) -> None:
        """Initialize the thermostat."""
        self._data = data
        self._device = device
        self._cool_away_temp = cool_away_temp
        self._heat_away_temp = heat_away_temp
        self._away = False
        self._retry = 0

        self._attr_unique_id = str(device.deviceid)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.deviceid)},
            name=device.name,
            manufacturer="Honeywell",
        )

        self._attr_translation_placeholders = {"name": device.name}
        self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        if device.temperature_unit == "C":
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_preset_modes = [PRESET_NONE, PRESET_AWAY, PRESET_HOLD]

        # not all honeywell HVACs support all modes

        self._hvac_mode_map = {
            key2: value2
            for key1, value1 in HVAC_MODE_TO_HW_MODE.items()
            if device.raw_ui_data[key1]
            for key2, value2 in value1.items()
        }
        self._attr_hvac_modes = list(self._hvac_mode_map)

        self._attr_supported_features = (
            ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        )
        if len(self.hvac_modes) > 1 and HVACMode.OFF in self.hvac_modes:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

        if device._data.get("canControlHumidification"):  # noqa: SLF001
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY

        if device.raw_ui_data.get("SwitchEmergencyHeatAllowed"):
            self._attr_supported_features |= ClimateEntityFeature.AUX_HEAT

        if not device._data.get("hasFan"):  # noqa: SLF001
            return

        # not all honeywell fans support all modes
        self._fan_mode_map = {
            key2: value2
            for key1, value1 in FAN_MODE_TO_HW.items()
            if device.raw_fan_data[key1]
            for key2, value2 in value1.items()
        }

        self._attr_fan_modes = list(self._fan_mode_map)

        self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device specific state attributes."""
        data: dict[str, Any] = {}
        data[ATTR_FAN_ACTION] = "running" if self._device.fan_running else "idle"
        data[ATTR_PERMANENT_HOLD] = self._is_permanent_hold()
        if self._device.raw_dr_data:
            data["dr_phase"] = self._device.raw_dr_data.get("Phase")
        return data

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self.hvac_mode == HVACMode.COOL:
            return self._device.raw_ui_data["CoolLowerSetptLimit"]
        if self.hvac_mode == HVACMode.HEAT:
            return self._device.raw_ui_data["HeatLowerSetptLimit"]
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return min(
                [
                    self._device.raw_ui_data["CoolLowerSetptLimit"],
                    self._device.raw_ui_data["HeatLowerSetptLimit"],
                ]
            )
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self.hvac_mode == HVACMode.COOL:
            return self._device.raw_ui_data["CoolUpperSetptLimit"]
        if self.hvac_mode == HVACMode.HEAT:
            return self._device.raw_ui_data["HeatUpperSetptLimit"]
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return max(
                [
                    self._device.raw_ui_data["CoolUpperSetptLimit"],
                    self._device.raw_ui_data["HeatUpperSetptLimit"],
                ]
            )
        return DEFAULT_MAX_TEMP

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._device.current_humidity

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        return HW_MODE_TO_HVAC_MODE.get(self._device.system_mode)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        if self.hvac_mode == HVACMode.OFF:
            return None
        return HW_MODE_TO_HA_HVAC_ACTION.get(self._device.equipment_output_status)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVACMode.COOL:
            return self._device.setpoint_cool
        if self.hvac_mode == HVACMode.HEAT:
            return self._device.setpoint_heat
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self._device.setpoint_cool
        return None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self._device.setpoint_heat
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._away:
            return PRESET_AWAY
        if self._is_permanent_hold():
            return PRESET_HOLD

        return PRESET_NONE

    @property
    def is_aux_heat(self) -> bool | None:
        """Return true if aux heater."""
        return self._device.system_mode == "emheat"

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return HW_FAN_MODE_TO_HA.get(self._device.fan_mode)

    def _is_permanent_hold(self) -> bool:
        heat_status = self._device.raw_ui_data.get("StatusHeat", 0)
        cool_status = self._device.raw_ui_data.get("StatusCool", 0)
        return heat_status == 2 or cool_status == 2

    async def _set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        try:
            # Get current mode
            mode = self._device.system_mode
            # Set hold if this is not the case
            if self._device.hold_heat is False and self._device.hold_cool is False:
                # Get next period time
                hour_heat, minute_heat = divmod(
                    self._device.raw_ui_data["HeatNextPeriod"] * 15, 60
                )
                hour_cool, minute_cool = divmod(
                    self._device.raw_ui_data["CoolNextPeriod"] * 15, 60
                )
                # Set temporary hold time and temperature
                if mode in COOLING_MODES:
                    await self._device.set_hold_cool(
                        datetime.time(hour_cool, minute_cool), temperature
                    )
                if mode in HEATING_MODES:
                    await self._device.set_hold_heat(
                        datetime.time(hour_heat, minute_heat), temperature
                    )

            # Set temperature if not in auto - set the temperature
            else:
                if mode == "cool":
                    await self._device.set_setpoint_cool(temperature)
                if mode in ["heat", "emheat"]:
                    await self._device.set_setpoint_heat(temperature)

        except (AscConnectionError, UnexpectedResponse) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="temp_failed",
            ) from err

        except SomeComfortError as err:
            _LOGGER.error("Invalid temperature %.1f: %s", temperature, err)
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="temp_failed_value",
                translation_placeholders={"temp": temperature},
            ) from err

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if {HVACMode.COOL, HVACMode.HEAT} & set(self._hvac_mode_map):
            await self._set_temperature(**kwargs)
            try:
                if temperature := kwargs.get(ATTR_TARGET_TEMP_HIGH):
                    await self._device.set_setpoint_cool(temperature)
                if temperature := kwargs.get(ATTR_TARGET_TEMP_LOW):
                    await self._device.set_setpoint_heat(temperature)

            except (AscConnectionError, UnexpectedResponse) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="temp_failed",
                ) from err

            except SomeComfortError as err:
                _LOGGER.error("Invalid temperature %.1f: %s", temperature, err)
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="temp_failed_value",
                    translation_placeholders={"temp": str(temperature)},
                ) from err

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        try:
            await self._device.set_fan_mode(self._fan_mode_map[fan_mode])

        except SomeComfortError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="fan_mode_failed",
            ) from err

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        try:
            await self._device.set_system_mode(self._hvac_mode_map[hvac_mode])

        except SomeComfortError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="sys_mode_failed",
            ) from err

    async def _turn_away_mode_on(self) -> None:
        """Turn away on.

        Somecomfort does have a proprietary away mode, but it doesn't really
        work the way it should. For example: If you set a temperature manually
        it doesn't get overwritten when away mode is switched on.
        """
        self._away = True
        # Get current mode
        mode = self._device.system_mode
        try:
            # Set permanent hold
            # and Set temperature
            if mode in COOLING_MODES:
                await self._device.set_hold_cool(True, self._cool_away_temp)
            if mode in HEATING_MODES:
                await self._device.set_hold_heat(True, self._heat_away_temp)

        except (AscConnectionError, UnexpectedResponse) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="away_mode_failed",
            ) from err

        except SomeComfortError as err:
            _LOGGER.error(
                "Temperature out of range. Mode: %s, Heat Temperature:  %.1f, Cool Temperature: %.1f",
                mode,
                self._heat_away_temp,
                self._cool_away_temp,
            )
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="temp_failed_range",
                translation_placeholders={
                    "heat": str(self._heat_away_temp),
                    "cool": str(self._cool_away_temp),
                    "mode": mode,
                },
            ) from err

    async def _turn_hold_mode_on(self) -> None:
        """Turn permanent hold on."""
        # Get current mode
        mode = self._device.system_mode
        # Check that we got a valid mode back
        if mode in HW_MODE_TO_HVAC_MODE:
            try:
                # Set permanent hold
                if mode in COOLING_MODES:
                    await self._device.set_hold_cool(True)
                if mode in HEATING_MODES:
                    await self._device.set_hold_heat(True)

            except SomeComfortError as err:
                _LOGGER.error("Couldn't set permanent hold")
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="set_hold_failed",
                ) from err
        else:
            _LOGGER.error("Invalid system mode returned: %s", mode)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_mode_failed",
                translation_placeholders={"mode": mode},
            )

    async def _turn_away_mode_off(self) -> None:
        """Turn away/hold off."""
        self._away = False
        try:
            # Disabling all hold modes
            await self._device.set_hold_cool(False)
            await self._device.set_hold_heat(False)

        except SomeComfortError as err:
            _LOGGER.error("Can not stop hold mode")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="stop_hold_failed",
            ) from err

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_AWAY:
            await self._turn_away_mode_on()
        elif preset_mode == PRESET_HOLD:
            self._away = False
            await self._turn_hold_mode_on()
        else:
            await self._turn_away_mode_off()

    async def async_turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            "service_deprecation",
            breaks_in_ha_version="2024.10.0",
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="service_deprecation",
        )
        try:
            await self._device.set_system_mode("emheat")

        except SomeComfortError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_aux_failed",
            ) from err

    async def async_turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""

        ir.async_create_issue(
            self.hass,
            DOMAIN,
            "service_deprecation",
            breaks_in_ha_version="2024.10.0",
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="service_deprecation",
        )

        try:
            if HVACMode.HEAT in self.hvac_modes:
                await self.async_set_hvac_mode(HVACMode.HEAT)
            else:
                await self.async_set_hvac_mode(HVACMode.OFF)

        except HomeAssistantError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="disable_aux_failed",
            ) from err

    async def async_update(self) -> None:
        """Get the latest state from the service."""

        async def _login() -> None:
            try:
                await self._data.client.login()
                await self._device.refresh()

            except (
                TimeoutError,
                AscConnectionError,
                APIRateLimited,
                AuthError,
                ClientConnectionError,
            ):
                self._retry += 1
                self._attr_available = self._retry <= RETRY
                return

            self._attr_available = True
            self._retry = 0

        try:
            await self._device.refresh()

        except UnauthorizedError:
            await _login()
            return
        except (
            TimeoutError,
            AscConnectionError,
            APIRateLimited,
            ClientConnectionError,
        ):
            self._retry += 1
            self._attr_available = self._retry <= RETRY
            return

        except UnexpectedResponse:
            return

        self._attr_available = True
        self._retry = 0
