"""Support for Toon binary sensors."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ToonDataUpdateCoordinator
from .models import (
    ToonBoilerDeviceEntity,
    ToonBoilerModuleDeviceEntity,
    ToonDisplayDeviceEntity,
    ToonEntity,
    ToonRequiredKeysMixin,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up a Toon binary sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        description.cls(coordinator, description)
        for description in BINARY_SENSOR_ENTITIES
    ]
    if coordinator.data.thermostat.have_opentherm_boiler:
        entities.extend(
            [
                description.cls(coordinator, description)
                for description in BINARY_SENSOR_ENTITIES_BOILER
            ]
        )

    async_add_entities(entities, True)


class ToonBinarySensor(ToonEntity, BinarySensorEntity):
    """Defines an Toon binary sensor."""

    entity_description: ToonBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: ToonDataUpdateCoordinator,
        description: ToonBinarySensorEntityDescription,
    ) -> None:
        """Initialize the Toon sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = (
            # This unique ID is a bit ugly and contains unneeded information.
            # It is here for legacy / backward compatible reasons.
            f"{DOMAIN}_{coordinator.data.agreement.agreement_id}_binary_sensor_{description.key}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return the status of the binary sensor."""
        section = getattr(self.coordinator.data, self.entity_description.section)
        value = getattr(section, self.entity_description.measurement)

        if value is None:
            return None

        if self.entity_description.inverted:
            return not value

        return value


class ToonBoilerBinarySensor(ToonBinarySensor, ToonBoilerDeviceEntity):
    """Defines a Boiler binary sensor."""


class ToonDisplayBinarySensor(ToonBinarySensor, ToonDisplayDeviceEntity):
    """Defines a Toon Display binary sensor."""


class ToonBoilerModuleBinarySensor(ToonBinarySensor, ToonBoilerModuleDeviceEntity):
    """Defines a Boiler module binary sensor."""


@dataclass
class ToonBinarySensorRequiredKeysMixin(ToonRequiredKeysMixin):
    """Mixin for binary sensor required keys."""

    cls: type[ToonBinarySensor]


@dataclass
class ToonBinarySensorEntityDescription(
    BinarySensorEntityDescription, ToonBinarySensorRequiredKeysMixin
):
    """Describes Toon binary sensor entity."""

    inverted: bool = False


BINARY_SENSOR_ENTITIES = (
    ToonBinarySensorEntityDescription(
        key="thermostat_info_boiler_connected_None",
        name="Boiler Module Connection",
        section="thermostat",
        measurement="boiler_module_connected",
        device_class=DEVICE_CLASS_CONNECTIVITY,
        entity_registry_enabled_default=False,
        cls=ToonBoilerModuleBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_program_overridden",
        name="Thermostat Program Override",
        section="thermostat",
        measurement="program_overridden",
        icon="mdi:gesture-tap",
        cls=ToonDisplayBinarySensor,
    ),
)

BINARY_SENSOR_ENTITIES_BOILER: tuple[ToonBinarySensorEntityDescription, ...] = (
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_1",
        name="Boiler Heating",
        section="thermostat",
        measurement="heating",
        icon="mdi:fire",
        entity_registry_enabled_default=False,
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_2",
        name="Hot Tap Water",
        section="thermostat",
        measurement="hot_tapwater",
        icon="mdi:water-pump",
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_3",
        name="Boiler Preheating",
        section="thermostat",
        measurement="pre_heating",
        icon="mdi:fire",
        entity_registry_enabled_default=False,
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_None",
        name="Boiler Burner",
        section="thermostat",
        measurement="burner",
        icon="mdi:fire",
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_error_found_255",
        name="Boiler Status",
        section="thermostat",
        measurement="error_found",
        device_class=DEVICE_CLASS_PROBLEM,
        icon="mdi:alert",
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_ot_communication_error_0",
        name="OpenTherm Connection",
        section="thermostat",
        measurement="opentherm_communication_error",
        device_class=DEVICE_CLASS_PROBLEM,
        icon="mdi:check-network-outline",
        entity_registry_enabled_default=False,
        cls=ToonBoilerBinarySensor,
    ),
)
