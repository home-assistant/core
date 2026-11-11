"""Support for Broadlink climate devices."""

from enum import IntEnum
from typing import Any, override

from broadlink_async.magic import (
    AC_FAN_AUTO,
    AC_FAN_HIGH,
    AC_FAN_LOW,
    AC_FAN_MEDIUM,
    AC_MODE_AUTO,
    AC_MODE_COOL,
    AC_MODE_DRY,
    AC_MODE_FAN,
    AC_MODE_HEAT,
    FLOOR_HEATING_MAX_TEMP,
    FLOOR_HEATING_MIN_TEMP,
    ImportedDevice,
    encode_floor_heating_attribute,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_HALVES, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    BROADLINK_DATA,
    DOMAIN,
    DOMAINS_AND_TYPES,
    is_magic_entry,
    magic_device_identifier,
    magic_rm_device_identifier,
)
from .coordinator import BroadLinkMagicConfigEntry, FamilyCoordinator
from .device import BroadlinkDevice
from .entity import BroadlinkEntity, BroadLinkMagicEntity, PendingCommands


class SensorMode(IntEnum):
    """Thermostat sensor modes."""

    INNER_SENSOR_CONTROL = 0
    OUTER_SENSOR_CONTROL = 1
    INNER_SENSOR_CONTROL_OUTER_LIMIT = 2


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Broadlink climate entities."""
    if is_magic_entry(config_entry):
        await _async_setup_magic_entry(hass, config_entry, async_add_entities)
        return

    device = hass.data[BROADLINK_DATA].devices[config_entry.entry_id]

    if device.api.type in DOMAINS_AND_TYPES[Platform.CLIMATE]:
        async_add_entities([BroadlinkThermostat(device)])


class BroadlinkThermostat(BroadlinkEntity, ClimateEntity):
    """Representation of a Broadlink Hysen climate entity."""

    _attr_has_entity_name = True

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the climate entity."""
        super().__init__(device)
        self._attr_unique_id = device.unique_id
        self._attr_hvac_mode = None
        self.sensor_mode = SensorMode.INNER_SENSOR_CONTROL

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self._device.async_request(self._device.api.set_temp, temperature)
        self._attr_native_target_temperature = temperature
        self.async_write_ha_state()

    @callback
    @override
    def _update_state(self, data: dict[str, Any]) -> None:
        """Update data."""
        if (sensor := data.get("sensor")) is not None:
            self.sensor_mode = SensorMode(sensor)
        if data.get("power"):
            if data.get("auto_mode"):
                self._attr_hvac_mode = HVACMode.AUTO
            else:
                self._attr_hvac_mode = HVACMode.HEAT

            if data.get("active"):
                self._attr_hvac_action = HVACAction.HEATING
            else:
                self._attr_hvac_action = HVACAction.IDLE
        else:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
        if self.sensor_mode is SensorMode.OUTER_SENSOR_CONTROL:
            self._attr_native_current_temperature = data.get("external_temp")
        else:
            self._attr_native_current_temperature = data.get("room_temp")
        self._attr_native_target_temperature = data.get("thermostat_temp")
        if (svl := data.get("svl")) is not None:
            self._attr_min_temp = svl
        if (svh := data.get("svh")) is not None:
            self._attr_max_temp = svh

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._device.async_request(self._device.api.set_power, 0)
        else:
            await self._device.async_request(self._device.api.set_power, 1)
            mode = 0 if hvac_mode == HVACMode.HEAT else 1
            # set_mode writes the register that the setpoint limits resend.
            async with self._device.settings_lock:
                await self._device.async_request(
                    self._device.api.set_mode, mode, 0, self.sensor_mode.value
                )

        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()


_HVAC_TO_RM = {
    HVACMode.AUTO: AC_MODE_AUTO,
    HVACMode.HEAT: AC_MODE_HEAT,
    HVACMode.COOL: AC_MODE_COOL,
    HVACMode.FAN_ONLY: AC_MODE_FAN,
    HVACMode.DRY: AC_MODE_DRY,
}
_FAN_TO_RM = {
    "auto": AC_FAN_AUTO,
    "low": AC_FAN_LOW,
    "medium": AC_FAN_MEDIUM,
    "high": AC_FAN_HIGH,
}
_RM_TO_HVAC = {value: key for key, value in _HVAC_TO_RM.items()}
_RM_TO_FAN = {value: key for key, value in _FAN_TO_RM.items()}


async def _async_setup_magic_entry(
    hass: HomeAssistant,
    entry: BroadLinkMagicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up imported gateway air conditioners and floor heating."""
    coordinator = entry.runtime_data
    entities: list[ClimateEntity] = [
        BroadLinkMagicClimate(coordinator, device)
        for device in coordinator.family.climate_devices
    ]
    entities.extend(
        BroadLinkMagicFloorHeating(coordinator, device)
        for device in coordinator.family.three_in_one_devices
    )
    async_add_entities(entities)


def _magic_climate_device_info(
    coordinator: FamilyCoordinator, device: ImportedDevice, via_device_id: str
) -> DeviceInfo:
    """Return the registry device of an imported air conditioner or panel."""
    if device.is_rm_child:
        identifier = magic_rm_device_identifier(device.stable_id)
        model = "Magic Home RM Air Conditioner"
    else:
        identifier = magic_device_identifier(device.stable_id)
        model = (
            "Magic Home 3-in-1 Thermostat"
            if device.is_three_in_one
            else "Magic Home Air Conditioner"
        )
    return DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        manufacturer="BroadLink",
        model=model,
        name=device.name,
        suggested_area=coordinator.room_name(device.room_id),
        via_device_id=via_device_id,
    )


class BroadLinkMagicClimate(BroadLinkMagicEntity, ClimateEntity):
    """An optimistic gateway infrared air conditioner."""

    _attr_fan_modes = list(_FAN_TO_RM)
    _attr_hvac_modes = [HVACMode.OFF, *_HVAC_TO_RM]
    _attr_hvac_mode = HVACMode.OFF
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_name = None
    _attr_precision = 1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_fan_mode = "auto"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_target_temperature = 24
    _attr_target_temperature_step = 1.0

    def __init__(
        self,
        coordinator: FamilyCoordinator,
        device: ImportedDevice,
    ) -> None:
        """Initialize an imported gateway climate entity."""
        super().__init__(coordinator)
        self._device = device
        self._area_name = coordinator.room_name(device.room_id)
        self._pending_state = PendingCommands()
        self._attr_unique_id = f"{coordinator.family.family_id}_{device.stable_id}"
        self._attr_device_info = _magic_climate_device_info(
            coordinator, device, self._family_device_id()
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Assign the imported room without overriding user changes."""
        await super().async_added_to_hass()
        if self._area_name and self.registry_entry is not None:
            device_id = self.registry_entry.device_id
            registry = dr.async_get(self.hass)
            device = registry.async_get(device_id) if device_id else None
            if device is not None and device.area_id is None:
                area = ar.async_get(self.hass).async_get_or_create(self._area_name)
                if isinstance(device, dr.ChildDeviceEntry):
                    registry.async_update_child_device(device.id, area_id=area.id)
                else:
                    registry.async_update_device(device.id, area_id=area.id)

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Apply a real FastCon status report."""
        state = self._confirmed_state(self._device, self._pending_state)
        power = state.get("power")
        if power == 0:
            self._attr_hvac_mode = HVACMode.OFF
        elif "mode" in state and (
            power == 1 or self._attr_hvac_mode is not HVACMode.OFF
        ):
            self._attr_hvac_mode = _RM_TO_HVAC.get(
                int(state["mode"]), self._attr_hvac_mode
            )
        if "temperature" in state:
            self._attr_native_target_temperature = int(state["temperature"])
        if "fan" in state:
            self._attr_fan_mode = _RM_TO_FAN.get(int(state["fan"]), self._attr_fan_mode)
        if "current_temperature" in state:
            self._attr_native_current_temperature = int(state["current_temperature"])
        super()._handle_coordinator_update()

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set power and HVAC mode."""
        if hvac_mode is HVACMode.OFF:
            commands = [("power", 0)]
        else:
            commands = [("power", 1), ("mode", _HVAC_TO_RM[hvac_mode])]
        await self.coordinator.async_send_ac(self._device, commands)
        self._pending_state.set("power", 0 if hvac_mode is HVACMode.OFF else 1)
        if hvac_mode is HVACMode.OFF:
            self._pending_state.discard("mode")
        else:
            self._pending_state.set("mode", _HVAC_TO_RM[hvac_mode])
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature and optionally HVAC mode."""
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_handle_set_hvac_mode_service(hvac_mode)
        temperature = round(float(kwargs[ATTR_TEMPERATURE]))
        await self.coordinator.async_send_ac(
            self._device, [("temperature", temperature)]
        )
        self._pending_state.set("temperature", temperature)
        self._attr_native_target_temperature = temperature
        self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan speed."""
        await self.coordinator.async_send_ac(
            self._device, [("fan", _FAN_TO_RM[fan_mode])]
        )
        self._pending_state.set("fan", _FAN_TO_RM[fan_mode])
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    @override
    async def async_turn_on(self) -> None:
        """Turn on using the last selected mode."""
        mode = (
            HVACMode.AUTO
            if self._attr_hvac_mode is HVACMode.OFF
            else self._attr_hvac_mode
        )
        await self.async_set_hvac_mode(mode)

    @override
    async def async_turn_off(self) -> None:
        """Turn off the air conditioner."""
        await self.async_set_hvac_mode(HVACMode.OFF)


class BroadLinkMagicFloorHeating(BroadLinkMagicEntity, ClimateEntity):
    """The floor-heating load of a three-in-one thermostat panel."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.OFF
    _attr_min_temp = FLOOR_HEATING_MIN_TEMP
    _attr_max_temp = FLOOR_HEATING_MAX_TEMP
    _attr_precision = 1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_translation_key = "floor_heating"

    def __init__(
        self,
        coordinator: FamilyCoordinator,
        device: ImportedDevice,
    ) -> None:
        """Initialize a floor-heating entity."""
        super().__init__(coordinator)
        self._device = device
        self._pending_state = PendingCommands()
        self._attr_unique_id = (
            f"{coordinator.family.family_id}_{device.stable_id}_floor_heating"
        )
        self._attr_device_info = _magic_climate_device_info(
            coordinator, device, self._family_device_id()
        )

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Apply a real three-in-one status report."""
        state = self._confirmed_state(self._device, self._pending_state)
        if "floor_heating_power" in state:
            self._attr_hvac_mode = (
                HVACMode.HEAT if state["floor_heating_power"] else HVACMode.OFF
            )
        if "floor_heating_temperature" in state:
            self._attr_native_target_temperature = int(
                state["floor_heating_temperature"]
            )
        if "current_temperature" in state:
            self._attr_native_current_temperature = int(state["current_temperature"])
        super()._handle_coordinator_update()

    async def _async_send(self, attribute: str, value: int) -> None:
        await self.coordinator.async_send_payloads(
            self._device, [encode_floor_heating_attribute(attribute, value)]
        )
        self._pending_state.set(f"floor_heating_{attribute}", value)

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn floor heating on or off."""
        await self._async_send("power", int(hvac_mode is HVACMode.HEAT))
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the floor-heating target temperature and optionally HVAC mode."""
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_handle_set_hvac_mode_service(hvac_mode)
        temperature = round(float(kwargs[ATTR_TEMPERATURE]))
        await self._async_send("temperature", temperature)
        self._attr_native_target_temperature = temperature
        self.async_write_ha_state()

    @override
    async def async_turn_on(self) -> None:
        """Turn floor heating on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    @override
    async def async_turn_off(self) -> None:
        """Turn floor heating off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
