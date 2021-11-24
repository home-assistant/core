"""Support for Tuya number."""
from __future__ import annotations

from typing import cast

from tuya_iot import TuyaDevice, TuyaDeviceManager
from tuya_iot.device import TuyaDeviceStatusRange

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import IntegerTypeData, TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode

# All descriptions can be found here. Mostly the Integer data types in the
# default instructions set of each category end up being a number.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
NUMBERS: dict[str, tuple[NumberEntityDescription, ...]] = {
    # Smart Kettle
    # https://developer.tuya.com/en/docs/iot/fbh?id=K9gf484m21yq7
    "bh": (
        NumberEntityDescription(
            key=DPCode.TEMP_SET,
            name="Temperature",
            icon="mdi:thermometer",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_SET_F,
            name="Temperature",
            icon="mdi:thermometer",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_BOILING_C,
            name="Temperature After Boiling",
            icon="mdi:thermometer",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_BOILING_F,
            name="Temperature After Boiling",
            icon="mdi:thermometer",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.WARM_TIME,
            name="Heat Preservation Time",
            icon="mdi:timer",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Human Presence Sensor
    # https://developer.tuya.com/en/docs/iot/categoryhps?id=Kaiuz42yhn1hs
    "hps": (
        NumberEntityDescription(
            key=DPCode.SENSITIVITY,
            name="Sensitivity",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.NEAR_DETECTION,
            name="Near Detection",
            icon="mdi:signal-distance-variant",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.FAR_DETECTION,
            name="Far Detection",
            icon="mdi:signal-distance-variant",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Coffee maker
    # https://developer.tuya.com/en/docs/iot/categorykfj?id=Kaiuz2p12pc7f
    "kfj": (
        NumberEntityDescription(
            key=DPCode.WATER_SET,
            name="Water Level",
            icon="mdi:cup-water",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_SET,
            name="Temperature",
            icon="mdi:thermometer",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.WARM_TIME,
            name="Heat Preservation Time",
            icon="mdi:timer",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.POWDER_SET,
            name="Powder",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Robot Vacuum
    # https://developer.tuya.com/en/docs/iot/fsd?id=K9gf487ck1tlo
    "sd": (
        NumberEntityDescription(
            key=DPCode.VOLUME_SET,
            name="Volume",
            icon="mdi:volume-high",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Siren Alarm
    # https://developer.tuya.com/en/docs/iot/categorysgbj?id=Kaiuz37tlpbnu
    "sgbj": (
        NumberEntityDescription(
            key=DPCode.ALARM_TIME,
            name="Time",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Smart Camera
    # https://developer.tuya.com/en/docs/iot/categorysp?id=Kaiuz35leyo12
    "sp": (
        NumberEntityDescription(
            key=DPCode.BASIC_DEVICE_VOLUME,
            name="Volume",
            icon="mdi:volume-high",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Dimmer Switch
    # https://developer.tuya.com/en/docs/iot/categorytgkg?id=Kaiuz0ktx7m0o
    "tgkg": (
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_1,
            name="Minimum Brightness",
            icon="mdi:lightbulb-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_1,
            name="Maximum Brightness",
            icon="mdi:lightbulb-on-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_2,
            name="Minimum Brightness 2",
            icon="mdi:lightbulb-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_2,
            name="Maximum Brightness 2",
            icon="mdi:lightbulb-on-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_3,
            name="Minimum Brightness 3",
            icon="mdi:lightbulb-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_3,
            name="Maximum Brightness 3",
            icon="mdi:lightbulb-on-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Dimmer Switch
    # https://developer.tuya.com/en/docs/iot/categorytgkg?id=Kaiuz0ktx7m0o
    "tgq": (
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_1,
            name="Minimum Brightness",
            icon="mdi:lightbulb-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_1,
            name="Maximum Brightness",
            icon="mdi:lightbulb-on-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_2,
            name="Minimum Brightness 2",
            icon="mdi:lightbulb-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_2,
            name="Maximum Brightness 2",
            icon="mdi:lightbulb-on-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Vibration Sensor
    # https://developer.tuya.com/en/docs/iot/categoryzd?id=Kaiuz3a5vrzno
    "zd": (
        NumberEntityDescription(
            key=DPCode.SENSITIVITY,
            name="Sensitivity",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya number dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya number."""
        entities: list[TuyaNumberEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := NUMBERS.get(device.category):
                for description in descriptions:
                    if (
                        description.key in device.function
                        or description.key in device.status
                    ):
                        entities.append(
                            TuyaNumberEntity(
                                device, hass_data.device_manager, description
                            )
                        )

        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaNumberEntity(TuyaEntity, NumberEntity):
    """Tuya Number Entity."""

    _status_range: TuyaDeviceStatusRange | None = None
    _type_data: IntegerTypeData | None = None

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: NumberEntityDescription,
    ) -> None:
        """Init Tuya sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        if status_range := device.status_range.get(description.key):
            self._status_range = cast(TuyaDeviceStatusRange, status_range)

            # Extract type data from integer status range,
            # and determine unit of measurement
            if self._status_range.type == "Integer":
                self._type_data = IntegerTypeData.from_json(self._status_range.values)
                self._attr_max_value = self._type_data.max_scaled
                self._attr_min_value = self._type_data.min_scaled
                self._attr_step = self._type_data.step_scaled
                if description.unit_of_measurement is None:
                    self._attr_unit_of_measurement = self._type_data.unit

    @property
    def value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        # Unknown or unsupported data type
        if self._status_range is None or self._status_range.type != "Integer":
            return None

        # Raw value
        value = self.device.status.get(self.entity_description.key)

        # Scale integer/float value
        if value and isinstance(self._type_data, IntegerTypeData):
            return self._type_data.scale_value(value)

        return None

    def set_value(self, value: float) -> None:
        """Set new value."""
        if self._type_data is None:
            raise RuntimeError("Cannot set value, device doesn't provide type data")

        self._send_command(
            [
                {
                    "code": self.entity_description.key,
                    "value": self._type_data.scale_value_back(value),
                }
            ]
        )
