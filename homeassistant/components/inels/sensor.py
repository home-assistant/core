"""iNELS sensor entity."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from operator import itemgetter
from typing import Any

from inelsmqtt.const import (  # Data types
    BATTERY,
    DA3_22M,
    DMD3_1,
    FA3_612M,
    GBP3_60,
    GRT3_50,
    GSB3_20SX,
    GSB3_40SX,
    GSB3_60SX,
    GSB3_90SX,
    IDRT3_1,
    IM3_20B,
    IM3_40B,
    IM3_80B,
    INELS_DEVICE_TYPE_DATA_STRUCT_DATA,
    RC3_610DALI,
    RFTI_10B,
    SA3_01B,
    SA3_02B,
    TEMP_IN,
    TEMP_OUT,
    TI3_10B,
    TI3_40B,
    TI3_60M,
    WSB3_20,
    WSB3_20H,
    WSB3_40,
    WSB3_40H,
)
from inelsmqtt.devices import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    Platform,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import InelsBaseEntity
from .const import (
    DEVICES,
    DOMAIN,
    ICON_BATTERY,
    ICON_DEW_POINT,
    ICON_FLASH,
    ICON_HUMIDITY,
    ICON_LIGHT_IN,
    ICON_TEMPERATURE,
)

bus_devices = [
    GRT3_50,
    WSB3_20H,
    WSB3_40H,
    WSB3_20,
    WSB3_40,
    IM3_20B,
    IM3_40B,
    IM3_80B,
    DMD3_1,
    TI3_10B,
    TI3_40B,
    TI3_60M,
    DA3_22M,
    SA3_01B,
    SA3_02B,
    GSB3_20SX,
    GSB3_40SX,
    GSB3_60SX,
    GSB3_90SX,
    IDRT3_1,
    GBP3_60,
    RC3_610DALI,
    FA3_612M,
]


@dataclass
class InelsSensorEntityDescriptionMixin:
    """Mixin keys."""

    value: Callable[[Device], Any | None]


@dataclass
class InelsSensorEntityDescription(
    SensorEntityDescription, InelsSensorEntityDescriptionMixin
):
    """Class for describing iNELS entities."""

    var: str | None = None
    index: int | None = None


@dataclass
class InelsBusSensorDescriptionMixin:
    """Mixin keys."""


@dataclass
class InelsBusSensorDescription(
    SensorEntityDescription, InelsBusSensorDescriptionMixin
):
    """Class for describing iNELS entities."""

    var: str | None = None
    index: int | None = None


def _process_data(data: str, indexes: list) -> str:
    """Process data for specific type of measurements."""
    array = data.split("\n")[:-1]
    data_range = itemgetter(*indexes)(array)
    range_joined = "".join(data_range)

    return f"0x{range_joined}"


def _process_value(val: str) -> str:
    middle_fs = True
    for k in val[1:-1]:
        if k.capitalize() != "F":
            middle_fs = False

    if (
        middle_fs
        and val[0] == "7"
        and ((val[-1] <= "F" and val[-1] >= "A") or val[-1] == "9")
    ):
        last = val[-1]
        if last == "9":
            return "Sensor not communicating"
        if last == "A":
            return "Sensor not calibrated"
        if last == "B":
            return "No value"
        if last == "C":
            return "Sensor not configured"
        if last == "D":
            return "Sensor value out of range"
        if last == "E":
            return "Sensor measurement error"
        if last == "F":
            return "No sensor connected"
        return "ERROR"

    return f"{float(int(val, 16))/100}"


def __get_battery_level(device: Device) -> int | None:
    """Get battery level of the device."""
    if device.is_available is False:
        return None

    # then get calculate the battery. In our case is 100 or 0
    return (
        100
        if int(
            _process_data(
                device.state,
                INELS_DEVICE_TYPE_DATA_STRUCT_DATA[device.inels_type][BATTERY],
            ),
            16,
        )
        == 0
        else 0
    )


def __get_temperature_in(device: Device) -> float | None:
    """Get temperature inside."""
    if device.is_available is False:
        return None

    return (
        int(
            _process_data(
                device.state,
                INELS_DEVICE_TYPE_DATA_STRUCT_DATA[device.inels_type][TEMP_IN],
            ),
            16,
        )
        / 100
    )


def __get_temperature_out(device: Device) -> float | None:
    """Get temperature outside."""
    if device.is_available is False:
        return None

    return (
        int(
            _process_data(
                device.state,
                INELS_DEVICE_TYPE_DATA_STRUCT_DATA[device.inels_type][TEMP_OUT],
            ),
            16,
        )
        / 100
    )


# RFTI_10B

SENSOR_DESCRIPTION_TEMPERATURE: tuple[InelsSensorEntityDescription, ...] = (
    InelsSensorEntityDescription(
        key="battery_level",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        icon=ICON_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value=__get_battery_level,
    ),
    InelsSensorEntityDescription(
        key="temp_in",
        name="Temperature In",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon=ICON_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # TEMP_CELSIUS,
        value=__get_temperature_in,
    ),
    InelsSensorEntityDescription(
        key="temp_out",
        name="Temperature Out",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon=ICON_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=__get_temperature_out,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load iNELS switch.."""
    device_list: list[Device] = hass.data[DOMAIN][config_entry.entry_id][DEVICES]

    entities: list[InelsBaseEntity] = []

    for device in device_list:
        if device.inels_type in bus_devices:
            val = device.get_value()
            if "temp_in" in val.ha_value.__dict__:
                entities.append(
                    InelsBusSensor(
                        device,
                        InelsBusSensorDescription(
                            key="temp_in",
                            name="Temperature",
                            icon=ICON_TEMPERATURE,
                            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                            var="temp_in",
                        ),
                    )
                )
            if "temp_out" in val.ha_value.__dict__:
                entities.append(
                    InelsBusSensor(
                        device,
                        InelsBusSensorDescription(
                            key="temp_out",
                            name="External temperature sensor",
                            icon=ICON_TEMPERATURE,
                            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                            var="temp_out",
                        ),
                    )
                )
            if "light_in" in val.ha_value.__dict__:
                entities.append(
                    InelsBusSensor(
                        device,
                        InelsBusSensorDescription(
                            key="light_in",
                            name="Light intensity",
                            icon=ICON_LIGHT_IN,
                            native_unit_of_measurement=LIGHT_LUX,
                            var="light_in",
                        ),
                    )
                )
            if "ain" in val.ha_value.__dict__:
                entities.append(
                    InelsBusSensor(
                        device,
                        InelsBusSensorDescription(
                            key="ain",
                            name="Analog temperature",
                            icon=ICON_TEMPERATURE,
                            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                            var="ain",
                        ),
                    )
                )
            if "humidity" in val.ha_value.__dict__:
                entities.append(
                    InelsBusSensor(
                        device,
                        InelsBusSensorDescription(
                            key="humidity",
                            name="Humidity",
                            icon=ICON_HUMIDITY,
                            native_unit_of_measurement=PERCENTAGE,
                            var="humidity",
                        ),
                    )
                )
            if "dewpoint" in val.ha_value.__dict__:
                entities.append(
                    InelsBusSensor(
                        device,
                        InelsBusSensorDescription(
                            key="dewpoint",
                            name="Dew point",
                            icon=ICON_DEW_POINT,
                            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                            var="dewpoint",
                        ),
                    )
                )
            if "temps" in val.ha_value.__dict__:
                for k in range(len(val.ha_value.temps)):
                    entities.append(
                        InelsBusSensor(
                            device,
                            InelsBusSensorDescription(
                                key=f"temp{k}",
                                name="Temperature",
                                icon=ICON_TEMPERATURE,
                                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                                var="temps",
                                index=k,
                            ),
                        )
                    )
            if "ains" in val.ha_value.__dict__:
                for k in range(len(val.ha_value.ains)):
                    entities.append(
                        InelsBusSensor(
                            device,
                            InelsBusSensorDescription(
                                key=f"ain{k}",
                                name="Analog input",
                                icon=ICON_FLASH,
                                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                                var="ains",
                                index=k,
                            ),
                        )
                    )
        else:
            descriptions: tuple[InelsSensorEntityDescription, ...]

            if device.device_type == Platform.SENSOR:
                if device.inels_type == RFTI_10B:
                    descriptions = SENSOR_DESCRIPTION_TEMPERATURE

            if descriptions is not None:
                for description in descriptions:
                    entities.append(InelsSensor(device, description=description))

    async_add_entities(entities, True)


class InelsSensor(InelsBaseEntity, SensorEntity):
    """The platform class required by Home Assistant."""

    entity_description: InelsSensorEntityDescription

    def __init__(
        self,
        device: Device,
        description: InelsSensorEntityDescription,
    ) -> None:
        """Initialize a sensor."""
        super().__init__(device=device)

        self.entity_description = description
        self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"
        if self.entity_description.index is not None:
            self._attr_unique_id += f"-{self.entity_description.index}"

        if description.name:
            self._attr_name = f"{self._attr_name} {description.name}"
            if self.entity_description.index is not None:
                self._attr_name += f" {self.entity_description.index + 1}"

        self._attr_native_value = self.entity_description.value(self._device)

    def _callback(self, new_value: Any) -> None:
        """Refresh data."""
        super()._callback(new_value)
        self._attr_native_value = self.entity_description.value(self._device)


class InelsBusSensor(InelsBaseEntity, SensorEntity):
    """Platform class for Home assistant, bus version."""

    entity_description: InelsBusSensorDescription

    def __init__(
        self,
        device: Device,
        description: InelsBusSensorDescription,
    ) -> None:
        """Initialize bus sensor."""
        super().__init__(device=device)

        self.entity_description = description
        self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"
        if self.entity_description.index is not None:
            self._attr_unique_id += f"-{self.entity_description.index}"

        if description.name:
            self._attr_name = f"{self._attr_name} {description.name}"
            if self.entity_description.index is not None:
                self._attr_name += f" {self.entity_description.index + 1}"

        if self.entity_description.index is not None:
            self._attr_native_value = _process_value(
                self._device.state.__dict__[self.entity_description.var][
                    self.entity_description.index
                ]
            )
        else:
            self._attr_native_value = _process_value(
                self._device.state.__dict__[self.entity_description.var]
            )

    def _callback(self, new_value: Any) -> None:
        """Refresh data."""
        super()._callback(new_value)

        if self.entity_description.index is not None:
            self._attr_native_value = _process_value(
                self._device.state.__dict__[self.entity_description.var][
                    self.entity_description.index
                ]
            )
        else:
            self._attr_native_value = _process_value(
                self._device.state.__dict__[self.entity_description.var]
            )
