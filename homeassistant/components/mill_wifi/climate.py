"""Climate capabilities setup."""

import asyncio
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import MillApiClient
from .common_entity import MillEntity
from .const import DOMAIN
from .coordinator import MillDataCoordinator
from .device_capability import DEVICE_CAPABILITY_MAP, EDeviceCapability, EDeviceType
from .device_metric import DeviceMetric

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Async setup method."""
    coordinator: MillDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: MillApiClient = hass.data[DOMAIN][entry.entry_id]["api"]
    entities = []

    if not coordinator.data:
        _LOGGER.warning("No data in coordinator during climate setup.")
        return

    for device_id, device_data in coordinator.data.items():
        if not device_data:
            _LOGGER.warning(
                "Device data missing for ID %s in climate setup.", device_id
            )
            continue

        device_type_name = DeviceMetric.get_device_type(device_data)
        if not device_type_name:
            _LOGGER.warning(
                "Could not determine device type for climate entity: %s", device_id
            )
            continue

        device_type_enum = None
        try:
            device_type_enum = EDeviceType(device_type_name)
        except ValueError:
            _LOGGER.warning(
                "Unsupported device type for climate entity: '%s' for device %s",
                device_type_name,
                device_id,
            )
            continue

        capabilities = DEVICE_CAPABILITY_MAP.get(device_type_enum, set())

        has_target_temp = EDeviceCapability.TARGET_TEMPERATURE in capabilities
        has_measure_temp = EDeviceCapability.MEASURE_TEMPERATURE in capabilities
        has_onoff = EDeviceCapability.ONOFF in capabilities

        if has_target_temp and has_measure_temp and has_onoff:
            entities.append(
                MillClimate(coordinator, api, device_id, capabilities, device_type_enum)
            )
        else:
            missing_caps = []
            if not has_target_temp:
                missing_caps.append("TARGET_TEMPERATURE")
            if not has_measure_temp:
                missing_caps.append("MEASURE_TEMPERATURE")
            if not has_onoff:
                missing_caps.append("ONOFF")

            _LOGGER.info(
                "Device %s (%s) will NOT create climate entity. Capabilities: %s. Missing required: %s. Has ONOFF: %s, Has TARGET_TEMP: %s, Has MEASURE_TEMP: %s",
                device_id,
                device_type_name,
                [cap.value for cap in capabilities],
                missing_caps,
                has_onoff,
                has_target_temp,
                has_measure_temp,
            )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d climate entities.", len(entities))
    else:
        _LOGGER.info(
            "No climate entities were added. Check previous INFO logs for reasons."
        )


class MillClimate(MillEntity, ClimateEntity):
    """Climate class."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    name = None
    _attr_assumed_state = True

    def __init__(
        self,
        coordinator: MillDataCoordinator,
        api: MillApiClient,
        device_id: str,
        capabilities: set[EDeviceCapability],
        device_type: EDeviceType,
    ):
        """Init method."""
        super().__init__(coordinator, device_id)
        self._api = api
        self._capabilities = capabilities
        self._device_type = device_type

        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_climate"

        self._is_socket = self._device_type in [
            EDeviceType.SOCKET_GEN2,
            EDeviceType.SOCKET_GEN3,
            EDeviceType.SOCKET_GEN4,
        ]

        if self._is_socket:
            self._attr_hvac_modes = [HVACMode.OFF]

            self._attr_hvac_modes.append(HVACMode.HEAT)
            if (
                self._device_type == EDeviceType.SOCKET_GEN4
                and EDeviceCapability.COOLING_MODE in self._capabilities
            ):
                self._attr_hvac_modes.append(HVACMode.COOL)
        else:
            self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
            if EDeviceCapability.COOLING_MODE in self._capabilities:
                self._attr_hvac_modes.append(HVACMode.COOL)

        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

        self._attr_target_temperature_step = 0.5
        if self._device_type == EDeviceType.HEATPUMP:
            self._attr_target_temperature_step = 1.0

        self._attr_min_temp = 5.0
        self._attr_max_temp = 35.0

        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_action = HVACAction.OFF

        self._update_internal_state()

    def _update_internal_state(self) -> None:  # noqa: C901
        """Update state method."""
        if not self._device:
            self._attr_hvac_action = HVACAction.OFF
            return

        current_temp_val = DeviceMetric.get_capability_value(
            self._device, EDeviceCapability.MEASURE_TEMPERATURE
        )
        try:
            self._attr_current_temperature = (
                float(current_temp_val) if current_temp_val is not None else None
            )
        except (ValueError, TypeError):
            self._attr_current_temperature = None

        server_target_temp_val = DeviceMetric.get_capability_value(
            self._device, EDeviceCapability.TARGET_TEMPERATURE
        )
        try:
            server_target_temperature = (
                float(server_target_temp_val)
                if server_target_temp_val is not None
                else None
            )
            if (
                self._attr_target_temperature is None
                or self._attr_target_temperature != server_target_temperature
            ):
                self._attr_target_temperature = server_target_temperature
        except (ValueError, TypeError):
            if self._attr_target_temperature is not None:
                self._attr_target_temperature = None

        power_on = DeviceMetric.get_power_state(self._device)

        server_hvac_mode = HVACMode.OFF
        if power_on:
            if (
                self._device_type == EDeviceType.SOCKET_GEN4
                and EDeviceCapability.COOLING_MODE in self._capabilities
            ):
                is_cooling_mode_active = bool(
                    DeviceMetric.get_capability_value(
                        self._device, EDeviceCapability.COOLING_MODE
                    )
                )
                if is_cooling_mode_active:
                    server_hvac_mode = HVACMode.COOL
                else:
                    server_hvac_mode = HVACMode.HEAT
            elif self._is_socket:
                server_hvac_mode = HVACMode.HEAT
            else:
                is_cooling_capable = (
                    EDeviceCapability.COOLING_MODE in self._capabilities
                )
                is_cooling_mode_active = False
                if is_cooling_capable:
                    is_cooling_mode_active = bool(
                        DeviceMetric.get_capability_value(
                            self._device, EDeviceCapability.COOLING_MODE
                        )
                    )

                if is_cooling_mode_active and HVACMode.COOL in self.hvac_modes:
                    server_hvac_mode = HVACMode.COOL
                elif HVACMode.HEAT in self.hvac_modes:
                    server_hvac_mode = HVACMode.HEAT

        if self._attr_hvac_mode is None or self._attr_hvac_mode != server_hvac_mode:
            self._attr_hvac_mode = server_hvac_mode

        new_hvac_action = HVACAction.OFF
        current_temp = self._attr_current_temperature
        target_temp = self._attr_target_temperature

        if self._attr_hvac_mode == HVACMode.HEAT:
            if power_on:
                if (
                    not self._is_socket
                    and self._device.get("lastMetrics", {}).get("heaterFlag") == 1
                ):
                    new_hvac_action = HVACAction.HEATING
                elif (
                    current_temp is not None
                    and target_temp is not None
                    and current_temp < target_temp
                ):
                    new_hvac_action = (
                        HVACAction.HEATING if not self._is_socket else HVACAction.IDLE
                    )
                    if self._is_socket:
                        new_hvac_action = HVACAction.IDLE

                    if self._is_socket:
                        new_hvac_action = HVACAction.HEATING

                elif (
                    current_temp is not None
                    and target_temp is not None
                    and current_temp >= target_temp
                ):
                    new_hvac_action = HVACAction.IDLE
                else:
                    new_hvac_action = HVACAction.IDLE if power_on else HVACAction.OFF
            else:
                new_hvac_action = HVACAction.OFF

        elif self._attr_hvac_mode == HVACMode.COOL:
            if power_on:
                if (
                    current_temp is not None
                    and target_temp is not None
                    and current_temp > target_temp
                ):
                    new_hvac_action = HVACAction.COOLING
                elif (
                    current_temp is not None
                    and target_temp is not None
                    and current_temp <= target_temp
                ):
                    new_hvac_action = HVACAction.IDLE
                else:
                    new_hvac_action = HVACAction.IDLE if power_on else HVACAction.OFF
            else:
                new_hvac_action = HVACAction.OFF

        if self._attr_hvac_action != new_hvac_action:
            self._attr_hvac_action = new_hvac_action

    @property
    def current_temperature(self) -> float | None:
        """Display current temperature."""

        return self._attr_current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Display current temperature."""
        return self._attr_target_temperature

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Display hvac mode."""
        return self._attr_hvac_mode

    @property
    def hvac_action(self) -> HVACAction | None:
        """Display hvac action."""
        return self._attr_hvac_action

    async def _delayed_refresh(self, delay_seconds: int):
        await asyncio.sleep(delay_seconds)
        if self.coordinator and self.hass:
            await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Update target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None or not self._device:
            return

        if EDeviceCapability.INDIVIDUAL_CONTROL in self._capabilities:
            individual_control_active = DeviceMetric.get_capability_value(
                self._device, EDeviceCapability.INDIVIDUAL_CONTROL
            )
            if not individual_control_active:
                _LOGGER.info(
                    "Cannot set temperature for %s. Individual control is not active. Attempting to enable it.",
                    self.entity_id,
                )
                try:
                    await self._api.set_switch_capability(
                        self._device_id,
                        EDeviceCapability.INDIVIDUAL_CONTROL.value,
                        True,
                        self._device,
                    )
                    _LOGGER.info(
                        "Individual control enabled for %s to set temperature.",
                        self.entity_id,
                    )
                    self.hass.async_create_task(
                        self._delayed_refresh(3)
                    )
                except Exception as e:  # noqa: BLE001
                    _LOGGER.error(
                        "Failed to enable individual control for %s: %s",
                        self.entity_id,
                        e,
                    )
                    return

        original_target_temp = self._attr_target_temperature
        self._attr_target_temperature = float(temp)
        if self._attr_hvac_mode == HVACMode.OFF:
            if (
                self._device_type == EDeviceType.SOCKET_GEN4
                and EDeviceCapability.COOLING_MODE in self._capabilities
                and bool(
                    DeviceMetric.get_capability_value(
                        self._device, EDeviceCapability.COOLING_MODE
                    )
                )
            ):
                self._attr_hvac_mode = HVACMode.COOL
            else:
                self._attr_hvac_mode = HVACMode.HEAT
        self.async_write_ha_state()

        try:
            if not DeviceMetric.get_power_state(self._device):
                await self._api.set_device_power(self._device_id, True, self._device)
                await asyncio.sleep(0.5)

            await self._api.set_number_capability(
                self._device_id,
                EDeviceCapability.TARGET_TEMPERATURE.value,
                temp,
                self._device,
            )
            self.hass.async_create_task(self._delayed_refresh(2))
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Error setting temperature for %s: %s", self._device_id, e)
            self._attr_target_temperature = original_target_temp
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Update hvac mode."""
        if not self._device:
            _LOGGER.error(
                "Cannot set HVAC mode for %s, device data not available.",
                self.entity_id,
            )
            return

        original_hvac_mode = self._attr_hvac_mode
        self._attr_hvac_mode = hvac_mode

        if hvac_mode == HVACMode.OFF:
            self._attr_hvac_action = HVACAction.OFF
        elif hvac_mode == HVACMode.HEAT:
            self._attr_hvac_action = HVACAction.HEATING
        elif hvac_mode == HVACMode.COOL:
            self._attr_hvac_action = HVACAction.COOLING
        self.async_write_ha_state()

        try:
            if hvac_mode == HVACMode.OFF:
                await self._api.set_device_power(self._device_id, False, self._device)
            elif hvac_mode == HVACMode.HEAT:
                await self._api.set_device_power(self._device_id, True, self._device)
                if (
                    self._device_type == EDeviceType.SOCKET_GEN4
                    and EDeviceCapability.COOLING_MODE in self._capabilities
                ):
                    current_cooling_state = DeviceMetric.get_capability_value(
                        self._device, EDeviceCapability.COOLING_MODE
                    )
                    if current_cooling_state:
                        await self._api.set_switch_capability(
                            self._device_id,
                            EDeviceCapability.COOLING_MODE.value,
                            False,
                            self._device,
                        )
            elif hvac_mode == HVACMode.COOL:
                if EDeviceCapability.COOLING_MODE in self._capabilities:
                    await self._api.set_device_power(
                        self._device_id, True, self._device
                    )
                    await self._api.set_switch_capability(
                        self._device_id,
                        EDeviceCapability.COOLING_MODE.value,
                        True,
                        self._device,
                    )
                else:
                    _LOGGER.warning(
                        "Attempted to set HVACMode.COOL for %s which does not support it.",
                        self.entity_id,
                    )
                    self._attr_hvac_mode = original_hvac_mode
                    self.async_write_ha_state()
                    return

            self.hass.async_create_task(self._delayed_refresh(3))
        except Exception as e:  # noqa: BLE001
            _LOGGER.error(
                "Error setting HVAC mode for %s to %s: %s",
                self._device_id,
                hvac_mode,
                e,
            )
            self._attr_hvac_mode = original_hvac_mode
            if self._attr_hvac_mode == HVACMode.OFF:
                self._attr_hvac_action = HVACAction.OFF
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_internal_state()
        super()._handle_coordinator_update()
