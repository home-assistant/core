"""Water Heater platform for Midea."""

from dataclasses import dataclass
from typing import Any, ClassVar, cast, override

from midealocal.device import DeviceType
from midealocal.devices.c3 import DeviceAttributes as C3Attributes, MideaC3Device
from midealocal.devices.cd import DeviceAttributes as CDAttributes, MideaCDDevice
from midealocal.devices.e2 import DeviceAttributes as E2Attributes, MideaE2Device
from midealocal.devices.e3 import DeviceAttributes as E3Attributes, MideaE3Device
from midealocal.devices.e6 import DeviceAttributes as E6Attributes, MideaE6Device

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    STATE_OFF,
    STATE_ON,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MideaConfigEntry, MideaEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class MideaWaterHeaterEntityDescription(WaterHeaterEntityDescription):
    """Description for a Midea water heater entity."""

    models: list[DeviceType]
    zone: int = 0


WATER_HEATERS: list[MideaWaterHeaterEntityDescription] = [
    MideaWaterHeaterEntityDescription(
        key="water_heater",
        translation_key="water_heater",
        models=[
            DeviceType.C3,
            DeviceType.CD,
            DeviceType.E2,
            DeviceType.E3,
        ],
    ),
    MideaWaterHeaterEntityDescription(
        key="water_heater_heating",
        translation_key="water_heater_heating",
        models=[
            DeviceType.E6,
        ],
    ),
    MideaWaterHeaterEntityDescription(
        key="water_heater_bathing",
        translation_key="water_heater_bathing",
        models=[
            DeviceType.E6,
        ],
        zone=1,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up water heater entries."""
    device = config_entry.runtime_data

    entities: list[MideaWaterHeater] = []
    for description in WATER_HEATERS:
        if device.device_type not in description.models:
            continue
        if device.device_type == DeviceType.E2:
            entities.append(
                MideaE2WaterHeater(cast("MideaE2Device", device), description)
            )
        elif device.device_type == DeviceType.E3:
            entities.append(
                MideaE3WaterHeater(cast("MideaE3Device", device), description)
            )
        elif device.device_type == DeviceType.E6:
            entities.append(
                MideaE6WaterHeater(cast("MideaE6Device", device), description)
            )
        elif device.device_type == DeviceType.C3:
            entities.append(
                MideaC3WaterHeater(cast("MideaC3Device", device), description)
            )
        elif device.device_type == DeviceType.CD:
            entities.append(
                MideaCDWaterHeater(cast("MideaCDDevice", device), description)
            )

    async_add_entities(entities)


type MideaWaterHeaterDevice = (
    MideaE2Device | MideaE3Device | MideaC3Device | MideaE6Device | MideaCDDevice
)


class MideaWaterHeater(MideaEntity, WaterHeaterEntity):
    """Midea Water Heater Entries Base Class."""

    _device: MideaWaterHeaterDevice

    def __init__(
        self,
        device: MideaWaterHeaterDevice,
        description: MideaWaterHeaterEntityDescription,
    ) -> None:
        """Midea Water Heater entity init."""
        super().__init__(device, description)
        self._operations: list[str] = []
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.ON_OFF
        )
        self._attr_precision = float(PRECISION_WHOLE)
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

    @property
    @override
    def target_temperature_step(self) -> float | None:
        """Return the supported target temperature step."""
        return cast("float | None", getattr(self._device, "temperature_step", None))

    @property
    @override
    def current_operation(self) -> str | None:
        """Midea Water Heater current operation."""
        return cast(
            "str",
            (
                self._device.get_attribute("mode")
                if self._device.get_attribute("power")
                else STATE_OFF
            ),
        )

    @property
    @override
    def current_temperature(self) -> float:
        """Midea Water Heater current temperature."""
        return cast("float", self._device.get_attribute("current_temperature"))

    @property
    @override
    def target_temperature(self) -> float:
        """Midea Water Heater target temperature."""
        return cast("float", self._device.get_attribute("target_temperature"))

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Midea Water Heater set temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        # input target_temperature should be float
        temperature = float(kwargs[ATTR_TEMPERATURE])
        self._device.set_attribute("target_temperature", temperature)

    @override
    def set_operation_mode(self, operation_mode: str) -> None:
        """Midea Water Heater set operation mode."""
        self._device.set_attribute(attr="mode", value=operation_mode)

    @property
    @override
    def operation_list(self) -> list[str] | None:
        """Midea Water Heater operation list."""
        return getattr(self._device, "preset_modes", None)

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Midea Water Heater turn on."""
        self._device.set_attribute(attr="power", value=True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Midea Water Heater turn off."""
        self._device.set_attribute(attr="power", value=False)


class MideaE2WaterHeater(MideaWaterHeater):
    """Midea E2 Water Heater Entries."""

    _device: MideaE2Device

    @property
    @override
    def current_operation(self) -> str:
        """Midea E2 Water Heater current operation."""
        return str(
            STATE_ON if self._device.get_attribute(E2Attributes.power) else STATE_OFF,
        )

    @property
    @override
    def min_temp(self) -> float:
        """Midea E2 Water Heater min temperature."""
        return cast("float", self._device.get_attribute(E2Attributes.temperature_min))

    @property
    @override
    def max_temp(self) -> float:
        """Midea E2 Water Heater max temperature."""
        return cast("float", self._device.get_attribute(E2Attributes.temperature_max))


class MideaE3WaterHeater(MideaWaterHeater):
    """Midea E3 Water Heater Entries."""

    _device: MideaE3Device

    @property
    @override
    def min_temp(self) -> float:
        """Midea E3 Water Heater min temperature."""
        return cast("float", self._device.get_attribute(E3Attributes.temperature_min))

    @property
    @override
    def max_temp(self) -> float:
        """Midea E3 Water Heater max temperature."""
        return cast("float", self._device.get_attribute(E3Attributes.temperature_max))

    @property
    @override
    def precision(self) -> float:
        """Midea E3 Water Heater precision."""
        return float(
            PRECISION_HALVES if self._device.precision_halves else PRECISION_WHOLE,
        )

    @property
    @override
    def current_operation(self) -> str:
        """Midea E3 Water Heater current operation."""
        return str(
            STATE_ON if self._device.get_attribute("power") else STATE_OFF,
        )


class MideaC3WaterHeater(MideaWaterHeater):
    """Midea C3 Water Heater Entries."""

    _device: MideaC3Device

    @property
    @override
    def current_operation(self) -> str:
        """Midea C3 Water Heater current operation."""
        return str(
            (
                STATE_ON
                if self._device.get_attribute(C3Attributes.dhw_power)
                else STATE_OFF
            ),
        )

    @property
    @override
    def current_temperature(self) -> float:
        """Midea C3 Water Heater current temperature."""
        return cast(
            "float",
            self._device.get_attribute(C3Attributes.tank_actual_temperature),
        )

    @property
    @override
    def target_temperature(self) -> float:
        """Midea C3 Water Heater target temperature."""
        return cast("float", self._device.get_attribute(C3Attributes.dhw_target_temp))

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Midea C3 Water Heater set temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        temperature = float(kwargs[ATTR_TEMPERATURE])
        self._device.set_attribute(C3Attributes.dhw_target_temp, temperature)

    @property
    @override
    def min_temp(self) -> float:
        """Midea C3 Water Heater min temperature."""
        return cast("float", self._device.get_attribute(C3Attributes.dhw_temp_min))

    @property
    @override
    def max_temp(self) -> float:
        """Midea C3 Water Heater max temperature."""
        return cast("float", self._device.get_attribute(C3Attributes.dhw_temp_max))

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Midea C3 Water Heater turn on."""
        self._device.set_attribute(attr=C3Attributes.dhw_power, value=True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Midea C3 Water Heater turn off."""
        self._device.set_attribute(attr=C3Attributes.dhw_power, value=False)


class MideaE6WaterHeater(MideaWaterHeater):
    """Midea E6 Water Heater Entries."""

    _device: MideaE6Device
    entity_description: MideaWaterHeaterEntityDescription

    _powers: ClassVar[list[E6Attributes]] = [
        E6Attributes.heating_power,
        E6Attributes.main_power,
    ]
    _current_temperatures: ClassVar[list[E6Attributes]] = [
        E6Attributes.heating_leaving_temperature,
        E6Attributes.bathing_leaving_temperature,
    ]
    _target_temperatures: ClassVar[list[E6Attributes]] = [
        E6Attributes.heating_temperature,
        E6Attributes.bathing_temperature,
    ]

    def __init__(
        self, device: MideaE6Device, description: MideaWaterHeaterEntityDescription
    ) -> None:
        """Midea E6 Water Heater entity init."""
        super().__init__(device, description)
        self._power_attr = MideaE6WaterHeater._powers[description.zone]
        self._current_temperature_attr = MideaE6WaterHeater._current_temperatures[
            description.zone
        ]
        self._target_temperature_attr = MideaE6WaterHeater._target_temperatures[
            description.zone
        ]
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.ON_OFF
        )
        if description.zone == 0:
            self._attr_supported_features |= (
                WaterHeaterEntityFeature.OPERATION_MODE
                | WaterHeaterEntityFeature.AWAY_MODE
            )

    @property
    @override
    def current_operation(self) -> str:
        """Midea E6 Water Heater current operation."""
        if self.entity_description.zone == 0:
            return (
                str(self._device.get_attribute(E6Attributes.heating_modes))
                if self._device.get_attribute(E6Attributes.main_power)
                and self._device.get_attribute(E6Attributes.heating_power)
                and self._device.get_attribute(E6Attributes.heating_modes) is not None
                else STATE_OFF
            )
        return (
            STATE_ON
            if self._device.get_attribute(E6Attributes.main_power)
            else STATE_OFF
        )

    @property
    @override
    def current_temperature(self) -> float:
        """Midea E6 Water Heater current temperature."""
        return cast("float", self._device.get_attribute(self._current_temperature_attr))

    @property
    @override
    def target_temperature(self) -> float:
        """Midea E6 Water Heater target temperature."""
        return cast("float", self._device.get_attribute(self._target_temperature_attr))

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Midea E6 Water Heater set temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        temperature = float(kwargs[ATTR_TEMPERATURE])
        self._device.set_attribute(self._target_temperature_attr, temperature)

    @override
    def set_operation_mode(self, operation_mode: str) -> None:
        """Midea Water Heater set operation mode."""
        self._device.set_attribute(
            attr=E6Attributes.heating_modes, value=operation_mode
        )

    @property
    @override
    def min_temp(self) -> float:
        """Midea E6 Water Heater min temperature."""
        min_temperature = cast(
            "list[float]",
            self._device.get_attribute(E6Attributes.temperature_min),
        )
        return min_temperature[self.entity_description.zone]

    @property
    @override
    def max_temp(self) -> float:
        """Midea E6 Water Heater max temperature."""
        max_temperature = cast(
            "list[float]",
            self._device.get_attribute(E6Attributes.temperature_max),
        )
        return max_temperature[self.entity_description.zone]

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Midea E6 Water Heater turn on."""
        self._device.set_attribute(attr=self._power_attr, value=True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Midea E6 Water Heater turn off."""
        self._device.set_attribute(attr=self._power_attr, value=False)

    @property
    @override
    def is_away_mode_on(self) -> bool:
        """Return whether E6 away mode is active."""
        return self._device.get_attribute(E6Attributes.heating_modes) == "out"

    @override
    def turn_away_mode_on(self) -> None:
        """Midea Water Heater turn away mode on."""
        self._device.set_attribute(attr=E6Attributes.heating_modes, value="out")

    @override
    def turn_away_mode_off(self) -> None:
        """Midea Water Heater turn away mode off."""
        self._device.set_attribute(
            attr=E6Attributes.heating_modes, value=self._device.preset_modes[0]
        )


class MideaCDWaterHeater(MideaWaterHeater):
    """Midea CD Water Heater Entries."""

    _device: MideaCDDevice

    @property
    @override
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Midea CD Water Heater supported features."""
        return (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
        )

    @property
    @override
    def min_temp(self) -> float:
        """Midea CD Water Heater min temperature."""
        return cast("float", self._device.get_attribute(CDAttributes.min_temperature))

    @property
    @override
    def max_temp(self) -> float:
        """Midea CD Water Heater max temperature."""
        return cast("float", self._device.get_attribute(CDAttributes.max_temperature))
