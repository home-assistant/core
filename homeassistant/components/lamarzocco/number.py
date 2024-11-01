"""Number platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from lmcloud.const import (
    KEYS_PER_MODEL,
    BoilerType,
    MachineModel,
    PhysicalKey,
    PrebrewMode,
)
from lmcloud.exceptions import RequestNotSuccessful
from lmcloud.lm_machine import LaMarzoccoMachine
from lmcloud.models import LaMarzoccoMachineConfig

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import (
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoConfigEntry, LaMarzoccoUpdateCoordinator
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoNumberEntityDescription(
    LaMarzoccoEntityDescription,
    NumberEntityDescription,
):
    """Description of a La Marzocco number entity."""

    native_value_fn: Callable[[LaMarzoccoMachineConfig], float | int]
    set_value_fn: Callable[[LaMarzoccoMachine, float | int], Coroutine[Any, Any, bool]]


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoKeyNumberEntityDescription(
    LaMarzoccoEntityDescription,
    NumberEntityDescription,
):
    """Description of an La Marzocco number entity with keys."""

    native_value_fn: Callable[[LaMarzoccoMachineConfig, PhysicalKey], float | int]
    set_value_fn: Callable[
        [LaMarzoccoMachine, float | int, PhysicalKey], Coroutine[Any, Any, bool]
    ]


ENTITIES: tuple[LaMarzoccoNumberEntityDescription, ...] = (
    LaMarzoccoNumberEntityDescription(
        key="coffee_temp",
        translation_key="coffee_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_step=PRECISION_TENTHS,
        native_min_value=85,
        native_max_value=104,
        set_value_fn=lambda machine, temp: machine.set_temp(BoilerType.COFFEE, temp),
        native_value_fn=lambda config: config.boilers[
            BoilerType.COFFEE
        ].target_temperature,
    ),
    LaMarzoccoNumberEntityDescription(
        key="steam_temp",
        translation_key="steam_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_step=PRECISION_WHOLE,
        native_min_value=126,
        native_max_value=131,
        set_value_fn=lambda machine, temp: machine.set_temp(BoilerType.STEAM, temp),
        native_value_fn=lambda config: config.boilers[
            BoilerType.STEAM
        ].target_temperature,
        supported_fn=lambda coordinator: coordinator.device.model
        in (
            MachineModel.GS3_AV,
            MachineModel.GS3_MP,
        ),
    ),
    LaMarzoccoNumberEntityDescription(
        key="tea_water_duration",
        translation_key="tea_water_duration",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_step=PRECISION_WHOLE,
        native_min_value=0,
        native_max_value=30,
        set_value_fn=lambda machine, value: machine.set_dose_tea_water(int(value)),
        native_value_fn=lambda config: config.dose_hot_water,
        supported_fn=lambda coordinator: coordinator.device.model
        in (
            MachineModel.GS3_AV,
            MachineModel.GS3_MP,
        ),
    ),
    LaMarzoccoNumberEntityDescription(
        key="smart_standby_time",
        translation_key="smart_standby_time",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_step=10,
        native_min_value=10,
        native_max_value=240,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda machine, value: machine.set_smart_standby(
            enabled=machine.config.smart_standby.enabled,
            mode=machine.config.smart_standby.mode,
            minutes=int(value),
        ),
        native_value_fn=lambda config: config.smart_standby.minutes,
    ),
)


KEY_ENTITIES: tuple[LaMarzoccoKeyNumberEntityDescription, ...] = (
    LaMarzoccoKeyNumberEntityDescription(
        key="prebrew_off",
        translation_key="prebrew_off",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_step=PRECISION_TENTHS,
        native_min_value=1,
        native_max_value=10,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda machine, value, key: machine.set_prebrew_time(
            prebrew_off_time=value, key=key
        ),
        native_value_fn=lambda config, key: config.prebrew_configuration[key].off_time,
        available_fn=lambda device: len(device.config.prebrew_configuration) > 0
        and device.config.prebrew_mode == PrebrewMode.PREBREW,
        supported_fn=lambda coordinator: coordinator.device.model
        != MachineModel.GS3_MP,
    ),
    LaMarzoccoKeyNumberEntityDescription(
        key="prebrew_on",
        translation_key="prebrew_on",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_step=PRECISION_TENTHS,
        native_min_value=2,
        native_max_value=10,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda machine, value, key: machine.set_prebrew_time(
            prebrew_on_time=value, key=key
        ),
        native_value_fn=lambda config, key: config.prebrew_configuration[key].off_time,
        available_fn=lambda device: len(device.config.prebrew_configuration) > 0
        and device.config.prebrew_mode == PrebrewMode.PREBREW,
        supported_fn=lambda coordinator: coordinator.device.model
        != MachineModel.GS3_MP,
    ),
    LaMarzoccoKeyNumberEntityDescription(
        key="preinfusion_off",
        translation_key="preinfusion_off",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_step=PRECISION_TENTHS,
        native_min_value=2,
        native_max_value=29,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda machine, value, key: machine.set_preinfusion_time(
            preinfusion_time=value, key=key
        ),
        native_value_fn=lambda config, key: config.prebrew_configuration[
            key
        ].preinfusion_time,
        available_fn=lambda device: len(device.config.prebrew_configuration) > 0
        and device.config.prebrew_mode == PrebrewMode.PREINFUSION,
        supported_fn=lambda coordinator: coordinator.device.model
        != MachineModel.GS3_MP,
    ),
    LaMarzoccoKeyNumberEntityDescription(
        key="dose",
        translation_key="dose",
        native_unit_of_measurement="ticks",
        native_step=PRECISION_WHOLE,
        native_min_value=0,
        native_max_value=999,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda machine, ticks, key: machine.set_dose(
            dose=int(ticks), key=key
        ),
        native_value_fn=lambda config, key: config.doses[key],
        supported_fn=lambda coordinator: coordinator.device.model
        == MachineModel.GS3_AV,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [
        LaMarzoccoNumberEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    ]

    for description in KEY_ENTITIES:
        if description.supported_fn(coordinator):
            num_keys = KEYS_PER_MODEL[MachineModel(coordinator.device.model)]
            entities.extend(
                LaMarzoccoKeyNumberEntity(coordinator, description, key)
                for key in range(min(num_keys, 1), num_keys + 1)
            )
    async_add_entities(entities)


class LaMarzoccoNumberEntity(LaMarzoccoEntity, NumberEntity):
    """La Marzocco number entity."""

    entity_description: LaMarzoccoNumberEntityDescription

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.entity_description.native_value_fn(self.coordinator.device.config)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        if value != self.native_value:
            try:
                await self.entity_description.set_value_fn(
                    self.coordinator.device, value
                )
            except RequestNotSuccessful as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="number_exception",
                    translation_placeholders={
                        "key": self.entity_description.key,
                        "value": str(value),
                    },
                ) from exc
            self.async_write_ha_state()


class LaMarzoccoKeyNumberEntity(LaMarzoccoEntity, NumberEntity):
    """Number representing espresso machine with key support."""

    entity_description: LaMarzoccoKeyNumberEntityDescription

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator,
        description: LaMarzoccoKeyNumberEntityDescription,
        pyhsical_key: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, description)

        # Physical Key on the machine the entity represents.
        if pyhsical_key == 0:
            pyhsical_key = 1
        else:
            self._attr_translation_key = f"{description.translation_key}_key"
            self._attr_translation_placeholders = {"key": str(pyhsical_key)}
            self._attr_unique_id = f"{super()._attr_unique_id}_key{pyhsical_key}"
            self._attr_entity_registry_enabled_default = False
        self.pyhsical_key = pyhsical_key

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.entity_description.native_value_fn(
            self.coordinator.device.config, PhysicalKey(self.pyhsical_key)
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        if value != self.native_value:
            try:
                await self.entity_description.set_value_fn(
                    self.coordinator.device, value, PhysicalKey(self.pyhsical_key)
                )
            except RequestNotSuccessful as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="number_exception_key",
                    translation_placeholders={
                        "key": self.entity_description.key,
                        "value": str(value),
                        "physical_key": str(self.pyhsical_key),
                    },
                ) from exc
            self.async_write_ha_state()
