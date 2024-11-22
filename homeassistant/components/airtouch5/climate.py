"""AirTouch 5 component to control AirTouch 5 Climate Devices."""

import logging
from typing import Any

from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient
from airtouch5py.packets.ac_ability import AcAbility
from airtouch5py.packets.ac_control import (
    AcControl,
    SetAcFanSpeed,
    SetAcMode,
    SetpointControl,
    SetPowerSetting,
)
from airtouch5py.packets.ac_status import AcFanSpeed, AcMode, AcPowerState, AcStatus
from airtouch5py.packets.zone_control import (
    ZoneControlZone,
    ZoneSettingPower,
    ZoneSettingValue,
)
from airtouch5py.packets.zone_name import ZoneName
from airtouch5py.packets.zone_status import ZonePowerState, ZoneStatusZone

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_FOCUS,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_BOOST,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Airtouch5ConfigEntry
from .const import DOMAIN, FAN_INTELLIGENT_AUTO, FAN_TURBO
from .entity import Airtouch5Entity

_LOGGER = logging.getLogger(__name__)

AC_MODE_TO_HVAC_MODE = {
    AcMode.AUTO: HVACMode.AUTO,
    AcMode.AUTO_COOL: HVACMode.AUTO,
    AcMode.AUTO_HEAT: HVACMode.AUTO,
    AcMode.COOL: HVACMode.COOL,
    AcMode.DRY: HVACMode.DRY,
    AcMode.FAN: HVACMode.FAN_ONLY,
    AcMode.HEAT: HVACMode.HEAT,
}
HVAC_MODE_TO_SET_AC_MODE = {
    HVACMode.AUTO: SetAcMode.SET_TO_AUTO,
    HVACMode.COOL: SetAcMode.SET_TO_COOL,
    HVACMode.DRY: SetAcMode.SET_TO_DRY,
    HVACMode.FAN_ONLY: SetAcMode.SET_TO_FAN,
    HVACMode.HEAT: SetAcMode.SET_TO_HEAT,
}


AC_FAN_SPEED_TO_FAN_SPEED = {
    AcFanSpeed.AUTO: FAN_AUTO,
    AcFanSpeed.QUIET: FAN_DIFFUSE,
    AcFanSpeed.LOW: FAN_LOW,
    AcFanSpeed.MEDIUM: FAN_MEDIUM,
    AcFanSpeed.HIGH: FAN_HIGH,
    AcFanSpeed.POWERFUL: FAN_FOCUS,
    AcFanSpeed.TURBO: FAN_TURBO,
    AcFanSpeed.INTELLIGENT_AUTO_1: FAN_INTELLIGENT_AUTO,
    AcFanSpeed.INTELLIGENT_AUTO_2: FAN_INTELLIGENT_AUTO,
    AcFanSpeed.INTELLIGENT_AUTO_3: FAN_INTELLIGENT_AUTO,
    AcFanSpeed.INTELLIGENT_AUTO_4: FAN_INTELLIGENT_AUTO,
    AcFanSpeed.INTELLIGENT_AUTO_5: FAN_INTELLIGENT_AUTO,
    AcFanSpeed.INTELLIGENT_AUTO_6: FAN_INTELLIGENT_AUTO,
}
FAN_MODE_TO_SET_AC_FAN_SPEED = {
    FAN_AUTO: SetAcFanSpeed.SET_TO_AUTO,
    FAN_DIFFUSE: SetAcFanSpeed.SET_TO_QUIET,
    FAN_LOW: SetAcFanSpeed.SET_TO_LOW,
    FAN_MEDIUM: SetAcFanSpeed.SET_TO_MEDIUM,
    FAN_HIGH: SetAcFanSpeed.SET_TO_HIGH,
    FAN_FOCUS: SetAcFanSpeed.SET_TO_POWERFUL,
    FAN_TURBO: SetAcFanSpeed.SET_TO_TURBO,
    FAN_INTELLIGENT_AUTO: SetAcFanSpeed.SET_TO_INTELLIGENT_AUTO,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: Airtouch5ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airtouch 5 Climate entities."""
    client = config_entry.runtime_data

    entities: list[ClimateEntity] = []

    # Add each AC (and remember what zones they apply to).
    # Each zone is controlled by a single AC
    zone_to_ac: dict[int, AcAbility] = {}
    for ac in client.ac:
        for i in range(ac.start_zone_number, ac.start_zone_number + ac.zone_count):
            zone_to_ac[i] = ac
        entities.append(Airtouch5AC(client, ac))

    # Add each zone
    entities.extend(
        Airtouch5Zone(client, zone, zone_to_ac[zone.zone_number])
        for zone in client.zones
    )

    async_add_entities(entities)


class Airtouch5ClimateEntity(ClimateEntity, Airtouch5Entity):
    """Base class for Airtouch5 Climate Entities."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN
    _attr_target_temperature_step = 1
    _attr_name = None
    _enable_turn_on_off_backwards_compatibility = False


class Airtouch5AC(Airtouch5ClimateEntity):
    """Representation of the AC unit. Used to control the overall HVAC Mode."""

    def __init__(self, client: Airtouch5SimpleClient, ability: AcAbility) -> None:
        """Initialise the Climate Entity."""
        super().__init__(client)
        self._ability = ability
        self._attr_unique_id = f"ac_{ability.ac_number}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"ac_{ability.ac_number}")},
            name=f"AC {ability.ac_number}",
            manufacturer="Polyaire",
            model="AirTouch 5",
        )
        self._attr_hvac_modes = [HVACMode.OFF]
        if ability.supports_mode_auto:
            self._attr_hvac_modes.append(HVACMode.AUTO)
        if ability.supports_mode_cool:
            self._attr_hvac_modes.append(HVACMode.COOL)
        if ability.supports_mode_dry:
            self._attr_hvac_modes.append(HVACMode.DRY)
        if ability.supports_mode_fan:
            self._attr_hvac_modes.append(HVACMode.FAN_ONLY)
        if ability.supports_mode_heat:
            self._attr_hvac_modes.append(HVACMode.HEAT)

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        if len(self.hvac_modes) > 1:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

        self._attr_fan_modes = []
        if ability.supports_fan_speed_quiet:
            self._attr_fan_modes.append(FAN_DIFFUSE)
        if ability.supports_fan_speed_low:
            self._attr_fan_modes.append(FAN_LOW)
        if ability.supports_fan_speed_medium:
            self._attr_fan_modes.append(FAN_MEDIUM)
        if ability.supports_fan_speed_high:
            self._attr_fan_modes.append(FAN_HIGH)
        if ability.supports_fan_speed_powerful:
            self._attr_fan_modes.append(FAN_FOCUS)
        if ability.supports_fan_speed_turbo:
            self._attr_fan_modes.append(FAN_TURBO)
        if ability.supports_fan_speed_auto:
            self._attr_fan_modes.append(FAN_AUTO)
        if ability.supports_fan_speed_intelligent_auto:
            self._attr_fan_modes.append(FAN_INTELLIGENT_AUTO)

        # We can have different setpoints for heat cool, we expose the lowest low and highest high
        self._attr_min_temp = min(
            ability.min_cool_set_point, ability.min_heat_set_point
        )
        self._attr_max_temp = max(
            ability.max_cool_set_point, ability.max_heat_set_point
        )

    @callback
    def _async_update_attrs(self, data: dict[int, AcStatus]) -> None:
        if self._ability.ac_number not in data:
            return
        status = data[self._ability.ac_number]

        self._attr_current_temperature = status.temperature
        self._attr_target_temperature = status.ac_setpoint
        if status.ac_power_state in [AcPowerState.OFF, AcPowerState.AWAY_OFF]:
            self._attr_hvac_mode = HVACMode.OFF
        else:
            self._attr_hvac_mode = AC_MODE_TO_HVAC_MODE[status.ac_mode]
        self._attr_fan_mode = AC_FAN_SPEED_TO_FAN_SPEED[status.ac_fan_speed]
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add data updated listener after this object has been initialized."""
        await super().async_added_to_hass()
        self._client.ac_status_callbacks.append(self._async_update_attrs)
        self._async_update_attrs(self._client.latest_ac_status)

    async def async_will_remove_from_hass(self) -> None:
        """Remove data updated listener after this object has been initialized."""
        await super().async_will_remove_from_hass()
        self._client.ac_status_callbacks.remove(self._async_update_attrs)

    async def _control(
        self,
        *,
        power: SetPowerSetting = SetPowerSetting.KEEP_POWER_SETTING,
        ac_mode: SetAcMode = SetAcMode.KEEP_AC_MODE,
        fan: SetAcFanSpeed = SetAcFanSpeed.KEEP_AC_FAN_SPEED,
        setpoint: SetpointControl = SetpointControl.KEEP_SETPOINT_VALUE,
        temp: int = 0,
    ) -> None:
        control = AcControl(
            power,
            self._ability.ac_number,
            ac_mode,
            fan,
            setpoint,
            temp,
        )
        packet = self._client.data_packet_factory.ac_control([control])
        await self._client.send_packet(packet)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        set_power_setting: SetPowerSetting
        set_ac_mode: SetAcMode

        if hvac_mode == HVACMode.OFF:
            set_power_setting = SetPowerSetting.SET_TO_OFF
            set_ac_mode = SetAcMode.KEEP_AC_MODE
        else:
            set_power_setting = SetPowerSetting.SET_TO_ON
            if hvac_mode not in HVAC_MODE_TO_SET_AC_MODE:
                raise ValueError(f"Unsupported hvac mode: {hvac_mode}")
            set_ac_mode = HVAC_MODE_TO_SET_AC_MODE[hvac_mode]

        await self._control(power=set_power_setting, ac_mode=set_ac_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if fan_mode not in FAN_MODE_TO_SET_AC_FAN_SPEED:
            raise ValueError(f"Unsupported fan mode: {fan_mode}")
        fan_speed = FAN_MODE_TO_SET_AC_FAN_SPEED[fan_mode]
        await self._control(fan=fan_speed)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            _LOGGER.debug("Argument `temperature` is missing in set_temperature")
            return

        await self._control(setpoint=SetpointControl.CHANGE_SETPOINT, temp=temp)


class Airtouch5Zone(Airtouch5ClimateEntity):
    """Representation of a Zone. Used to control the AC effect in the zone."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.FAN_ONLY]
    _attr_preset_modes = [PRESET_NONE, PRESET_BOOST]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(
        self, client: Airtouch5SimpleClient, name: ZoneName, ac: AcAbility
    ) -> None:
        """Initialise the Climate Entity."""
        super().__init__(client)
        self._name = name

        self._attr_unique_id = f"zone_{name.zone_number}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"zone_{name.zone_number}")},
            name=name.zone_name,
            manufacturer="Polyaire",
            model="AirTouch 5",
        )
        # We can have different setpoints for heat and cool, we expose the lowest low and highest high
        self._attr_min_temp = min(ac.min_cool_set_point, ac.min_heat_set_point)
        self._attr_max_temp = max(ac.max_cool_set_point, ac.max_heat_set_point)

    @callback
    def _async_update_attrs(self, data: dict[int, ZoneStatusZone]) -> None:
        if self._name.zone_number not in data:
            return
        status = data[self._name.zone_number]
        self._attr_current_temperature = status.temperature
        self._attr_target_temperature = status.set_point

        if status.zone_power_state == ZonePowerState.OFF:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_preset_mode = PRESET_NONE
        elif status.zone_power_state == ZonePowerState.ON:
            self._attr_hvac_mode = HVACMode.FAN_ONLY
            self._attr_preset_mode = PRESET_NONE
        elif status.zone_power_state == ZonePowerState.TURBO:
            self._attr_hvac_mode = HVACMode.FAN_ONLY
            self._attr_preset_mode = PRESET_BOOST
        else:
            self._attr_hvac_mode = None

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add data updated listener after this object has been initialized."""
        await super().async_added_to_hass()
        self._client.zone_status_callbacks.append(self._async_update_attrs)
        self._async_update_attrs(self._client.latest_zone_status)

    async def async_will_remove_from_hass(self) -> None:
        """Remove data updated listener after this object has been initialized."""
        await super().async_will_remove_from_hass()
        self._client.zone_status_callbacks.remove(self._async_update_attrs)

    async def _control(
        self,
        *,
        zsv: ZoneSettingValue = ZoneSettingValue.KEEP_SETTING_VALUE,
        power: ZoneSettingPower = ZoneSettingPower.KEEP_POWER_STATE,
        value: float = 0,
    ) -> None:
        control = ZoneControlZone(self._name.zone_number, zsv, power, value)
        packet = self._client.data_packet_factory.zone_control([control])
        await self._client.send_packet(packet)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        power: ZoneSettingPower

        if hvac_mode is HVACMode.OFF:
            power = ZoneSettingPower.SET_TO_OFF
        elif self._attr_preset_mode is PRESET_BOOST:
            power = ZoneSettingPower.SET_TO_TURBO
        else:
            power = ZoneSettingPower.SET_TO_ON

        await self._control(power=power)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Enable or disable Turbo. Done this way as we can't have a turbo HVACMode."""
        power: ZoneSettingPower
        if preset_mode == PRESET_BOOST:
            power = ZoneSettingPower.SET_TO_TURBO
        else:
            power = ZoneSettingPower.SET_TO_ON

        await self._control(power=power)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""

        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            _LOGGER.debug("Argument `temperature` is missing in set_temperature")
            return

        await self._control(
            zsv=ZoneSettingValue.SET_TARGET_SETPOINT,
            value=float(temp),
        )

    async def async_turn_on(self) -> None:
        """Turn the zone on."""
        await self.async_set_hvac_mode(HVACMode.FAN_ONLY)

    async def async_turn_off(self) -> None:
        """Turn the zone off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
