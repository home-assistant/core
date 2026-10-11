"""Platform for number integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from boschshcpy import (
    SHCMicromoduleRelay,
    SHCShutterContact2,
    SHCSmartPlug,
    SHCSmartPlugCompact,
)
from boschshcpy.device import SHCDevice

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SHCNumberEntityDescription[_DeviceT: SHCDevice](NumberEntityDescription):
    """Describes a SHC number entity."""

    value_fn: Callable[[_DeviceT], float | None]
    set_value_fn: Callable[[_DeviceT, float], None]


def _impulse_length_value_fn(device: SHCMicromoduleRelay) -> float | None:
    # ImpulseSwitchService.impulse_length indexes the raw state dict
    # directly, so a partial poll that omits the field raises KeyError,
    # not just AttributeError.
    try:
        raw = device.impulse_length
    except AttributeError, KeyError:
        return None
    if raw is None:
        return None
    return float(raw) / 10.0


def _impulse_length_set_value_fn(device: SHCMicromoduleRelay, value: float) -> None:
    device.impulse_length = round(value * 10)


def _power_threshold_set_value_fn(
    device: SHCSmartPlug | SHCSmartPlugCompact, value: float
) -> None:
    device.power_threshold = value


def _enter_duration_set_value_fn(
    device: SHCSmartPlug | SHCSmartPlugCompact, value: float
) -> None:
    device.enter_duration_seconds = round(value)


IMPULSE_LENGTH = "impulse_length"

NUMBER_TYPES: dict[str, SHCNumberEntityDescription] = {
    IMPULSE_LENGTH: SHCNumberEntityDescription[SHCMicromoduleRelay](
        key=IMPULSE_LENGTH,
        translation_key=IMPULSE_LENGTH,
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0.1,
        native_max_value=60.0,
        native_step=0.1,
        mode=NumberMode.BOX,
        value_fn=_impulse_length_value_fn,
        set_value_fn=_impulse_length_set_value_fn,
    ),
    "bypass_timeout": SHCNumberEntityDescription[SHCShutterContact2](
        key="bypass_timeout",
        translation_key="bypass_timeout",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=1.0,
        native_max_value=15.0,
        native_step=1.0,
        mode=NumberMode.BOX,
        value_fn=lambda device: float(device.bypass_timeout),
        set_value_fn=lambda device, value: device.set_bypass_configuration(
            timeout=round(value)
        ),
    ),
    "power_threshold": SHCNumberEntityDescription[SHCSmartPlug | SHCSmartPlugCompact](
        key="power_threshold",
        translation_key="energy_saving_power_threshold",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0.0,
        native_max_value=3680.0,
        native_step=1.0,
        mode=NumberMode.BOX,
        value_fn=lambda device: device.power_threshold,
        set_value_fn=_power_threshold_set_value_fn,
    ),
    "enter_duration": SHCNumberEntityDescription[SHCSmartPlug | SHCSmartPlugCompact](
        key="enter_duration",
        translation_key="energy_saving_enter_duration",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=1.0,
        native_max_value=3600.0,
        native_step=1.0,
        mode=NumberMode.BOX,
        value_fn=lambda device: float(device.enter_duration_seconds),
        set_value_fn=_enter_duration_set_value_fn,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC number platform."""
    session = config_entry.runtime_data
    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    entities: list[SHCNumber] = []
    for device in session.device_helper.micromodule_impulse_relays:
        # KeyError means a partial poll temporarily omits the field, not that
        # the device is unsupported, so the entity is still created with an
        # unknown state until a later poll or callback fills it in.
        try:
            supported = device.impulse_length is not None
        except KeyError:
            supported = True
        if not supported:
            continue
        entities.append(
            SHCNumber(
                hass=hass,
                device=device,
                parent_id=shc_info.unique_id,
                entry_id=config_entry.entry_id,
                description=NUMBER_TYPES[IMPULSE_LENGTH],
            )
        )

    entities.extend(
        SHCNumber(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=NUMBER_TYPES["bypass_timeout"],
        )
        for device in session.device_helper.shutter_contacts2
    )

    entities.extend(
        SHCNumber(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=NUMBER_TYPES["power_threshold"],
        )
        for device in session.device_helper.smart_plugs
        if device.supports_energy_saving_mode and device.power_threshold is not None
    )
    entities.extend(
        SHCNumber(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=NUMBER_TYPES["enter_duration"],
        )
        for device in session.device_helper.smart_plugs
        if device.supports_energy_saving_mode
        and device.enter_duration_seconds is not None
    )
    entities.extend(
        SHCNumber(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=NUMBER_TYPES["power_threshold"],
        )
        for device in session.device_helper.smart_plugs_compact
        if device.supports_energy_saving_mode and device.power_threshold is not None
    )
    entities.extend(
        SHCNumber(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=NUMBER_TYPES["enter_duration"],
        )
        for device in session.device_helper.smart_plugs_compact
        if device.supports_energy_saving_mode
        and device.enter_duration_seconds is not None
    )

    async_add_entities(entities)


class SHCNumber[_DeviceT: SHCDevice](SHCEntity, NumberEntity):
    """Generic SHC number entity, driven by a SHCNumberEntityDescription."""

    entity_description: SHCNumberEntityDescription[_DeviceT]
    _device: _DeviceT

    def __init__(
        self,
        hass: HomeAssistant,
        device: _DeviceT,
        parent_id: str,
        entry_id: str,
        description: SHCNumberEntityDescription[_DeviceT],
    ) -> None:
        """Initialize the number entity."""
        self.entity_description = description
        super().__init__(
            hass=hass, device=device, parent_id=parent_id, entry_id=entry_id
        )
        self._attr_unique_id = f"{device.serial}_{description.key}"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self._device)

    @override
    def set_native_value(self, value: float) -> None:
        """Set a new value, writing it to the device."""
        self.entity_description.set_value_fn(self._device, value)
