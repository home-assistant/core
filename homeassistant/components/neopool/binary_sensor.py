"""Binary sensor platform for the NeoPool integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from neopool_modbus.capabilities import (
    has_heating_relay,
    is_chlorine_module_present,
    is_conductivity_module_present,
    is_hydrolysis_present,
    is_ionization_present,
    is_ph_module_present,
    is_redox_module_present,
)
from neopool_modbus.registers import is_valid_relay_gpio

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_USE_AUX1,
    CONF_USE_AUX2,
    CONF_USE_AUX3,
    CONF_USE_AUX4,
    CONF_USE_COVER_SENSOR,
    CONF_USE_LIGHT,
)
from .coordinator import NeoPoolConfigEntry, NeoPoolCoordinator
from .entity import NeoPoolEntity

PARALLEL_UPDATES = 0

type _SupportedFn = Callable[[dict[str, Any]], bool]


@dataclass(frozen=True, kw_only=True)
class NeoPoolBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a NeoPool binary sensor entity."""

    supported_fn: _SupportedFn | None = None
    value_fn: Callable[[dict[str, Any], HomeAssistant], bool | None] | None = None


def _gpio_ok(gpio_key: str) -> _SupportedFn:
    """Return a supported_fn that checks a relay GPIO key is valid."""
    return lambda data: gpio_key not in data or is_valid_relay_gpio(data[gpio_key] or 0)


def _pool_cover_open(data: dict[str, Any], hass: HomeAssistant) -> bool | None:
    """Invert the raw cover state for the OPENING device class.

    The cover bit is only valid while filtration runs; otherwise report unknown.
    """
    if data.get("Filtration Pump") is not True:
        return None
    value = data.get("Pool Cover")
    if value is None:
        return None
    return not bool(value)


BINARY_SENSOR_DESCRIPTIONS: dict[str, NeoPoolBinarySensorEntityDescription] = {
    "pH Acid Pump": NeoPoolBinarySensorEntityDescription(
        key="pH Acid Pump",
        translation_key="ph_acid_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=_gpio_ok("MBF_PAR_PH_ACID_RELAY_GPIO"),
    ),
    "Filtration Pump": NeoPoolBinarySensorEntityDescription(
        key="Filtration Pump",
        translation_key="filtration_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        supported_fn=_gpio_ok("MBF_PAR_FILT_GPIO"),
    ),
    "Pool Light": NeoPoolBinarySensorEntityDescription(
        key="Pool Light",
        translation_key="pool_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        supported_fn=_gpio_ok("MBF_PAR_LIGHTING_GPIO"),
    ),
    "AUX1": NeoPoolBinarySensorEntityDescription(
        key="AUX1",
        translation_key="aux",
        translation_placeholders={"number": "1"},
        device_class=BinarySensorDeviceClass.POWER,
    ),
    "AUX2": NeoPoolBinarySensorEntityDescription(
        key="AUX2",
        translation_key="aux",
        translation_placeholders={"number": "2"},
        device_class=BinarySensorDeviceClass.POWER,
    ),
    "AUX3": NeoPoolBinarySensorEntityDescription(
        key="AUX3",
        translation_key="aux",
        translation_placeholders={"number": "3"},
        device_class=BinarySensorDeviceClass.POWER,
    ),
    "AUX4": NeoPoolBinarySensorEntityDescription(
        key="AUX4",
        translation_key="aux",
        translation_placeholders={"number": "4"},
        device_class=BinarySensorDeviceClass.POWER,
    ),
    "pH module control status": NeoPoolBinarySensorEntityDescription(
        key="pH module control status",
        translation_key="ph_module_control_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_ph_module_present,
    ),
    "pH control module": NeoPoolBinarySensorEntityDescription(
        key="pH control module",
        translation_key="ph_control_module",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_ph_module_present,
    ),
    "pH measurement active": NeoPoolBinarySensorEntityDescription(
        key="pH measurement active",
        translation_key="ph_measurement_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_ph_module_present,
    ),
    "Redox pump active": NeoPoolBinarySensorEntityDescription(
        key="Redox pump active",
        translation_key="redox_pump_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=lambda data: (
            is_redox_module_present(data)
            and (
                "MBF_PAR_RX_RELAY_GPIO" not in data
                or is_valid_relay_gpio(data["MBF_PAR_RX_RELAY_GPIO"] or 0)
            )
        ),
    ),
    "Redox control module": NeoPoolBinarySensorEntityDescription(
        key="Redox control module",
        translation_key="redox_control_module",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_redox_module_present,
    ),
    "Redox measurement active": NeoPoolBinarySensorEntityDescription(
        key="Redox measurement active",
        translation_key="redox_measurement_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_redox_module_present,
    ),
    "Chlorine flow sensor problem": NeoPoolBinarySensorEntityDescription(
        key="Chlorine flow sensor problem",
        translation_key="chlorine_flow_sensor_problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=is_chlorine_module_present,
    ),
    "Chlorine pump active": NeoPoolBinarySensorEntityDescription(
        key="Chlorine pump active",
        translation_key="chlorine_pump_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=lambda data: (
            is_chlorine_module_present(data)
            and (
                "MBF_PAR_CL_RELAY_GPIO" not in data
                or is_valid_relay_gpio(data["MBF_PAR_CL_RELAY_GPIO"] or 0)
            )
        ),
    ),
    "Chlorine control module": NeoPoolBinarySensorEntityDescription(
        key="Chlorine control module",
        translation_key="chlorine_control_module",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_chlorine_module_present,
    ),
    "Chlorine measurement active": NeoPoolBinarySensorEntityDescription(
        key="Chlorine measurement active",
        translation_key="chlorine_measurement_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_chlorine_module_present,
    ),
    "Conductivity pump active": NeoPoolBinarySensorEntityDescription(
        key="Conductivity pump active",
        translation_key="conductivity_pump_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=lambda data: (
            is_conductivity_module_present(data)
            and (
                "MBF_PAR_CD_RELAY_GPIO" not in data
                or is_valid_relay_gpio(data["MBF_PAR_CD_RELAY_GPIO"] or 0)
            )
        ),
    ),
    "Conductivity control module": NeoPoolBinarySensorEntityDescription(
        key="Conductivity control module",
        translation_key="conductivity_control_module",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_conductivity_module_present,
    ),
    "Conductivity measurement active": NeoPoolBinarySensorEntityDescription(
        key="Conductivity measurement active",
        translation_key="conductivity_measurement_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_conductivity_module_present,
    ),
    "ION On Target": NeoPoolBinarySensorEntityDescription(
        key="ION On Target",
        translation_key="ion_on_target",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_ionization_present,  # pragma: no cover
    ),
    "ION Low": NeoPoolBinarySensorEntityDescription(
        key="ION Low",
        translation_key="ion_low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=is_ionization_present,  # pragma: no cover
    ),
    "ION Program time exceeded": NeoPoolBinarySensorEntityDescription(
        key="ION Program time exceeded",
        translation_key="ion_program_time_exceeded",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=is_ionization_present,  # pragma: no cover
    ),
    "HIDRO Low": NeoPoolBinarySensorEntityDescription(
        key="HIDRO Low",
        translation_key="hidro_low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=is_hydrolysis_present,
    ),
    "Pool Cover": NeoPoolBinarySensorEntityDescription(
        key="Pool Cover",
        translation_key="pool_cover",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=_pool_cover_open,
    ),
    "HIDRO Module active": NeoPoolBinarySensorEntityDescription(
        key="HIDRO Module active",
        translation_key="hidro_module_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=is_hydrolysis_present,
    ),
    "HIDRO Module regulated": NeoPoolBinarySensorEntityDescription(
        key="HIDRO Module regulated",
        translation_key="hidro_module_regulated",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_hydrolysis_present,
    ),
    "HIDRO Activated by the RX module": NeoPoolBinarySensorEntityDescription(
        key="HIDRO Activated by the RX module",
        translation_key="hidro_activated_by_the_rx_module",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=lambda data: (
            is_hydrolysis_present(data) and is_redox_module_present(data)
        ),  # pragma: no cover
    ),
    "HIDRO Chlorine shock mode": NeoPoolBinarySensorEntityDescription(
        key="HIDRO Chlorine shock mode",
        translation_key="hidro_chlorine_shock_mode",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=is_hydrolysis_present,
    ),
    "HIDRO Activated by the CL module": NeoPoolBinarySensorEntityDescription(
        key="HIDRO Activated by the CL module",
        translation_key="hidro_activated_by_the_cl_module",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=lambda data: (
            is_hydrolysis_present(data) and is_chlorine_module_present(data)
        ),
    ),
    "Heating": NeoPoolBinarySensorEntityDescription(
        key="Heating",
        translation_key="heating",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=has_heating_relay,
    ),
    "UV Lamp": NeoPoolBinarySensorEntityDescription(
        key="UV Lamp",
        translation_key="uv_lamp",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=lambda data: (
            "MBF_PAR_UV_RELAY_GPIO" not in data
            or is_valid_relay_gpio(data["MBF_PAR_UV_RELAY_GPIO"] or 0)
        ),
    ),
}


# Entities gated on a config-entry option (in addition to their supported_fn).
# The controller cannot detect what is physically wired to the light or aux
# relays, nor whether a cover sensor is present, so these entities are opt-in
# per config entry rather than surfaced from a device capability bit.
_ENTITY_OPTION_KEY: dict[str, str] = {
    "Pool Light": CONF_USE_LIGHT,
    "AUX1": CONF_USE_AUX1,
    "AUX2": CONF_USE_AUX2,
    "AUX3": CONF_USE_AUX3,
    "AUX4": CONF_USE_AUX4,
    "Pool Cover": CONF_USE_COVER_SENSOR,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NeoPool binary sensors from a config entry."""
    coordinator = entry.runtime_data
    options = entry.options

    async_add_entities(
        NeoPoolBinarySensor(coordinator, key, desc)
        for key, desc in BINARY_SENSOR_DESCRIPTIONS.items()
        if (
            (option_key := _ENTITY_OPTION_KEY.get(key)) is None
            or bool(options.get(option_key))
        )
        and (desc.supported_fn is None or desc.supported_fn(coordinator.data))
    )


class NeoPoolBinarySensor(NeoPoolEntity, BinarySensorEntity):
    """Representation of a NeoPool binary sensor."""

    _winter_mode_active = False
    entity_description: NeoPoolBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NeoPoolCoordinator,
        key: str,
        description: NeoPoolBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._key = key
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.unique_id}_{key.lower()}"
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        if (value_fn := self.entity_description.value_fn) is not None:
            value: bool | None = value_fn(self.coordinator.data, self.hass)
            return value
        value = self.coordinator.data.get(self._key)
        return None if value is None else bool(value)
