import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberDeviceClass, NumberMode
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant, callback 
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device_capability import DEVICE_CAPABILITY_MAP, EDeviceCapability, EDeviceType
from .device_metric import DeviceMetric
from .coordinator import MillDataCoordinator
from .api import MillApiClient
from .common_entity import MillEntity

_LOGGER = logging.getLogger(__name__)

NUMBER_TYPES: dict[EDeviceCapability, tuple[str, str | None, float, float, float, NumberDeviceClass | None, NumberMode, str | None]] = {
    EDeviceCapability.TARGET_TEMPERATURE: (
        "Target Temperature",
        UnitOfTemperature.CELSIUS,
        5,
        35,
        0.5,
        NumberDeviceClass.TEMPERATURE,
        NumberMode.SLIDER,
        None
    ),
    EDeviceCapability.ADJUST_WATTAGE: (
        "Max Power Limit",
        PERCENTAGE,
        10,
        100,
        10,
        None,
        NumberMode.SLIDER,
        "mdi:speedometer"
    ),
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MillDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: MillApiClient = hass.data[DOMAIN][entry.entry_id]["api"]
    entities = []

    if not coordinator.data:
        _LOGGER.warning("No data in coordinator during number setup.")
        return

    for device_id, device_data in coordinator.data.items():
        if not device_data:
            continue

        device_type_name = DeviceMetric.get_device_type(device_data)
        if not device_type_name:
            _LOGGER.warning("Could not determine device type for number entity: %s", device_id)
            continue
        
        try:
            device_type_enum = EDeviceType(device_type_name)
        except ValueError:
            _LOGGER.warning("Unsupported device type for number entity: %s for device %s", device_type_name, device_id)
            continue

        capabilities = DEVICE_CAPABILITY_MAP.get(device_type_enum, set())

        for cap_enum, (name_suffix, unit, min_val, max_val, step, dev_class, mode, icon) in NUMBER_TYPES.items():
            if cap_enum in capabilities:
                if cap_enum == EDeviceCapability.TARGET_TEMPERATURE:
                    if EDeviceCapability.MEASURE_TEMPERATURE not in capabilities or \
                        EDeviceCapability.ONOFF not in capabilities:
                            entities.append(MillNumber(coordinator, api, device_id, cap_enum, name_suffix, unit, min_val, max_val, step, dev_class, mode, icon))
                else:
                    entities.append(MillNumber(coordinator, api, device_id, cap_enum, name_suffix, unit, min_val, max_val, step, dev_class, mode, icon))

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.info("No number entities added.")


class MillNumber(MillEntity, NumberEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillDataCoordinator,
        api: MillApiClient,
        device_id: str,
        capability: EDeviceCapability,
        name_suffix: str,
        unit: str | None,
        min_value: float,
        max_value: float,
        step: float,
        device_class: NumberDeviceClass | None,
        mode: NumberMode = NumberMode.AUTO, 
        icon: str | None = None
    ):
        super().__init__(coordinator, device_id, capability)
        self._api = api
        self.name = name_suffix

        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_device_class = device_class
        self._attr_mode = mode
        self._attr_icon = icon
        self._attr_native_value = None 

        self._update_internal_state()


    def _update_internal_state(self) -> None:
        if not self._device:
            self._attr_native_value = None
            return
        
        value = DeviceMetric.get_capability_value(self._device, self._capability)
        new_native_value = None
        try:
            new_native_value = float(value) if value is not None else None
        except (ValueError, TypeError):
            _LOGGER.debug("Could not parse number value '%s' for %s", value, self.entity_id)
            new_native_value = None
        
        if self._attr_native_value != new_native_value:
            self._attr_native_value = new_native_value
        
    @property
    def native_value(self) -> float | None:
        return self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        if not self._device:
            _LOGGER.error("Cannot set number value for %s, device data not available.", self.entity_id)
            return
        try:
            await self._api.set_number_capability(self._device_id, self._capability.value, value, self._device)
            await self.coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.error("Error setting number value for %s on %s: %s", self._capability.value, self._device_id, e)

    @callback
    def _handle_coordinator_update(self) -> None: 
        self._update_internal_state()
        super()._handle_coordinator_update()
