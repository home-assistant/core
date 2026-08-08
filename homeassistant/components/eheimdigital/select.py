"""EHEIM Digital select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, override

from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.filter import EheimDigitalFilter
from eheimdigital.reeflex import EheimDigitalReeflexUV
from eheimdigital.types import (
    FilterMode,
    FilterModeProf,
    ReeflexMode,
    UnitOfMeasurement as EheimDigitalUnitOfMeasurement,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import (
    EntityCategory,
    Platform,
    UnitOfFrequency,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import homeassistant.helpers.entity_registry as er

from . import DOMAIN
from .coordinator import EheimDigitalConfigEntry, EheimDigitalDeviceUpdateCoordinator
from .entity import EheimDigitalEntity, exception_handler

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EheimDigitalSelectDescription[_DeviceT: EheimDigitalDevice](
    SelectEntityDescription
):
    """Class describing EHEIM Digital select entities."""

    options_fn: Callable[[_DeviceT], list[str]] | None = None
    use_api_unit: Literal[True] | None = None
    value_fn: Callable[[_DeviceT], str | None]
    set_value_fn: Callable[[_DeviceT, str], Awaitable[None] | None]


REEFLEX_DESCRIPTIONS: tuple[
    EheimDigitalSelectDescription[EheimDigitalReeflexUV], ...
] = (
    EheimDigitalSelectDescription[EheimDigitalReeflexUV](
        key="mode",
        translation_key="mode",
        value_fn=lambda device: device.mode.name.lower(),
        set_value_fn=(
            lambda device, value: device.set_mode(ReeflexMode[value.upper()])
        ),
        options=[name.lower() for name in ReeflexMode.__members__],
    ),
)

FILTER_DESCRIPTIONS: tuple[EheimDigitalSelectDescription[EheimDigitalFilter], ...] = (
    EheimDigitalSelectDescription[EheimDigitalFilter](
        key="filter_mode",
        translation_key="filter_mode",
        entity_category=EntityCategory.CONFIG,
        options=[item.lower() for item in FilterModeProf._member_names_],
        value_fn=lambda device: device.filter_mode.name.lower(),
        set_value_fn=lambda device, value: device.set_filter_mode(
            FilterModeProf[value.upper()]
        ),
    ),
    EheimDigitalSelectDescription[EheimDigitalFilter](
        key="manual_speed",
        translation_key="manual_speed",
        entity_category=EntityCategory.CONFIG,
        unit_of_measurement=UnitOfFrequency.HERTZ,
        options_fn=lambda device: [str(i) for i in device.filter_manual_values],
        value_fn=lambda device: str(device.manual_speed),
        set_value_fn=lambda device, value: device.set_manual_speed(float(value)),
    ),
    EheimDigitalSelectDescription[EheimDigitalFilter](
        key="const_flow",
        translation_key="const_flow",
        entity_category=EntityCategory.CONFIG,
        use_api_unit=True,
        unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        options_fn=lambda device: [str(i) for i in device.filter_const_flow_values],
        value_fn=lambda device: str(device.filter_const_flow_values[device.const_flow]),
        set_value_fn=(
            lambda device, value: device.set_const_flow(
                device.filter_const_flow_values.index(int(value))
            )
        ),
    ),
    EheimDigitalSelectDescription[EheimDigitalFilter](
        key="day_speed",
        translation_key="day_speed",
        entity_category=EntityCategory.CONFIG,
        use_api_unit=True,
        unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        options_fn=lambda device: [str(i) for i in device.filter_const_flow_values],
        value_fn=lambda device: str(device.filter_const_flow_values[device.day_speed]),
        set_value_fn=(
            lambda device, value: device.set_day_speed(
                device.filter_const_flow_values.index(int(value))
            )
        ),
    ),
    EheimDigitalSelectDescription[EheimDigitalFilter](
        key="night_speed",
        translation_key="night_speed",
        entity_category=EntityCategory.CONFIG,
        use_api_unit=True,
        unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        options_fn=lambda device: [str(i) for i in device.filter_const_flow_values],
        value_fn=lambda device: str(
            device.filter_const_flow_values[device.night_speed]
        ),
        set_value_fn=(
            lambda device, value: device.set_night_speed(
                device.filter_const_flow_values.index(int(value))
            )
        ),
    ),
    EheimDigitalSelectDescription[EheimDigitalFilter](
        key="high_pulse_speed",
        translation_key="high_pulse_speed",
        entity_category=EntityCategory.CONFIG,
        use_api_unit=True,
        unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        options_fn=lambda device: [str(i) for i in device.filter_const_flow_values],
        value_fn=lambda device: str(
            device.filter_const_flow_values[device.high_pulse_speed]
        ),
        set_value_fn=(
            lambda device, value: device.set_high_pulse_speed(
                device.filter_const_flow_values.index(int(value))
            )
        ),
    ),
    EheimDigitalSelectDescription[EheimDigitalFilter](
        key="low_pulse_speed",
        translation_key="low_pulse_speed",
        entity_category=EntityCategory.CONFIG,
        use_api_unit=True,
        unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        options_fn=lambda device: [str(i) for i in device.filter_const_flow_values],
        value_fn=lambda device: str(
            device.filter_const_flow_values[device.low_pulse_speed]
        ),
        set_value_fn=(
            lambda device, value: device.set_low_pulse_speed(
                device.filter_const_flow_values.index(int(value))
            )
        ),
    ),
)


CLASSICVARIO_DESCRIPTIONS: tuple[
    EheimDigitalSelectDescription[EheimDigitalClassicVario], ...
] = (
    EheimDigitalSelectDescription[EheimDigitalClassicVario](
        key="filter_mode",
        translation_key="filter_mode",
        value_fn=lambda device: device.filter_mode.name.lower(),
        set_value_fn=(
            lambda device, value: device.set_filter_mode(FilterMode[value.upper()])
        ),
        options=[name.lower() for name in FilterMode.__members__],
    ),
)


def _async_migrate_entities(hass: HomeAssistant, device_address: str) -> None:
    registry = er.async_get(hass)
    if (
        old_id := registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, f"{device_address}_const_flow_speed"
        )
    ) is not None:
        registry.async_update_entity(
            old_id, new_unique_id=old_id.replace("const_flow_speed", "const_flow")
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EheimDigitalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up callbacks to add select entities as devices are found."""
    coordinator = entry.runtime_data

    def async_setup_device_entities(
        device_coordinator: EheimDigitalDeviceUpdateCoordinator[Any],
    ) -> None:
        """Set up the number entities for one or multiple devices."""
        entities: list[EheimDigitalSelect[Any]] = []
        _async_migrate_entities(hass, device_coordinator.data.mac_address)
        if isinstance(device_coordinator.data, EheimDigitalClassicVario):
            entities.extend(
                EheimDigitalSelect[EheimDigitalClassicVario](
                    device_coordinator, description
                )
                for description in CLASSICVARIO_DESCRIPTIONS
                if description.key
                in device_coordinator.data.packet_mapping[device_coordinator.msg_title]
            )
        if isinstance(device_coordinator.data, EheimDigitalFilter):
            entities.extend(
                EheimDigitalFilterSelect(device_coordinator, description)
                for description in FILTER_DESCRIPTIONS
                if description.key
                in device_coordinator.data.packet_mapping[device_coordinator.msg_title]
            )
        if isinstance(device_coordinator.data, EheimDigitalReeflexUV):
            entities.extend(
                EheimDigitalSelect[EheimDigitalReeflexUV](
                    device_coordinator, description
                )
                for description in REEFLEX_DESCRIPTIONS
                if description.key
                in device_coordinator.data.packet_mapping[device_coordinator.msg_title]
            )

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)


class EheimDigitalSelect[_DeviceT: EheimDigitalDevice](
    EheimDigitalEntity[_DeviceT], SelectEntity
):
    """Represent an EHEIM Digital select entity."""

    entity_description: EheimDigitalSelectDescription[_DeviceT]

    _attr_options: list[str]

    def __init__(
        self,
        coordinator: EheimDigitalDeviceUpdateCoordinator[_DeviceT],
        description: EheimDigitalSelectDescription[_DeviceT],
    ) -> None:
        """Initialize an EHEIM Digital select entity."""
        super().__init__(coordinator)
        self.entity_description = description
        if description.options_fn is not None:
            self._attr_options = description.options_fn(self._device)
        elif description.options is not None:
            self._attr_options = description.options
        self._attr_unique_id = f"{self._device_address}_{description.key}"

    @override
    @exception_handler
    async def async_select_option(self, option: str) -> None:
        if await_return := self.entity_description.set_value_fn(self._device, option):
            return await await_return
        return None

    @override
    def _async_update_attrs(self) -> None:
        self._attr_current_option = self.entity_description.value_fn(self._device)


class EheimDigitalFilterSelect(EheimDigitalSelect[EheimDigitalFilter]):
    """Represent an EHEIM Digital Filter select entity."""

    entity_description: EheimDigitalSelectDescription[EheimDigitalFilter]
    _attr_native_unit_of_measurement: str | None

    @override
    def _async_update_attrs(self) -> None:
        if (
            self.entity_description.options is None
            and self.entity_description.options_fn is not None
        ):
            self._attr_options = self.entity_description.options_fn(self._device)
        if self.entity_description.use_api_unit:
            if (
                self.entity_description.unit_of_measurement
                == UnitOfVolumeFlowRate.LITERS_PER_HOUR
                and self._device.usrdta["unit"]
                == int(EheimDigitalUnitOfMeasurement.US_CUSTOMARY)
            ):
                self._attr_native_unit_of_measurement = (
                    UnitOfVolumeFlowRate.GALLONS_PER_HOUR
                )
        else:
            self._attr_native_unit_of_measurement = (
                self.entity_description.unit_of_measurement
            )
        super()._async_update_attrs()
