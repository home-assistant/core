"""Support for Enphase Envoy solar energy monitor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from operator import attrgetter

from pyenphase import EnvoyC6CC, EnvoyCollar, EnvoyEncharge, EnvoyEnpower

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import EnphaseConfigEntry, EnphaseUpdateCoordinator
from .entity import EnvoyBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EnvoyEnchargeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Envoy Encharge binary sensor entity."""

    value_fn: Callable[[EnvoyEncharge], bool]


ENCHARGE_SENSORS = (
    EnvoyEnchargeBinarySensorEntityDescription(
        key="communicating",
        translation_key="communicating",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=attrgetter("communicating"),
    ),
    EnvoyEnchargeBinarySensorEntityDescription(
        key="dc_switch",
        translation_key="dc_switch",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda encharge: not encharge.dc_switch_off,
    ),
)


@dataclass(frozen=True, kw_only=True)
class EnvoyEnpowerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Envoy Enpower binary sensor entity."""

    value_fn: Callable[[EnvoyEnpower], bool]


ENPOWER_SENSORS = (
    EnvoyEnpowerBinarySensorEntityDescription(
        key="communicating",
        translation_key="communicating",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=attrgetter("communicating"),
    ),
    EnvoyEnpowerBinarySensorEntityDescription(
        key="mains_oper_state",
        translation_key="grid_status",
        value_fn=lambda enpower: enpower.mains_oper_state == "closed",
    ),
)


@dataclass(frozen=True, kw_only=True)
class EnvoyCollarBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Envoy IQ Meter Collar binary sensor entity."""

    value_fn: Callable[[EnvoyCollar], bool]


COLLAR_SENSORS = (
    EnvoyCollarBinarySensorEntityDescription(
        key="communicating",
        translation_key="communicating",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=attrgetter("communicating"),
    ),
)


@dataclass(frozen=True, kw_only=True)
class EnvoyC6CCBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an C6 Combiner controller binary sensor entity."""

    value_fn: Callable[[EnvoyC6CC], bool]


C6CC_SENSORS = (
    EnvoyC6CCBinarySensorEntityDescription(
        key="communicating",
        translation_key="communicating",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=attrgetter("communicating"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnphaseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up envoy binary sensor platform."""
    coordinator = config_entry.runtime_data
    envoy_data = coordinator.envoy.data
    assert envoy_data is not None
    entities: list[BinarySensorEntity] = []
    if envoy_data.encharge_inventory:
        entities.extend(
            EnvoyEnchargeBinarySensorEntity(coordinator, description, encharge)
            for description in ENCHARGE_SENSORS
            for encharge in envoy_data.encharge_inventory
        )

    if envoy_data.enpower:
        entities.extend(
            EnvoyEnpowerBinarySensorEntity(coordinator, description)
            for description in ENPOWER_SENSORS
        )

    if envoy_data.collar:
        entities.extend(
            EnvoyCollarBinarySensorEntity(coordinator, description)
            for description in COLLAR_SENSORS
        )

    if envoy_data.c6cc:
        entities.extend(
            EnvoyC6CCBinarySensorEntity(coordinator, description)
            for description in C6CC_SENSORS
        )

    async_add_entities(entities)


class EnvoyBaseBinarySensorEntity(EnvoyBaseEntity, BinarySensorEntity):
    """Defines a base envoy binary_sensor entity."""


class EnvoyEnchargeBinarySensorEntity(EnvoyBaseBinarySensorEntity):
    """Defines an Encharge binary_sensor entity."""

    entity_description: EnvoyEnchargeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyEnchargeBinarySensorEntityDescription,
        serial_number: str,
    ) -> None:
        """Init the Encharge base entity."""
        super().__init__(coordinator, description)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{description.key}"
        encharge_inventory = self.data.encharge_inventory
        assert encharge_inventory is not None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="Enphase",
            model="Encharge",
            name=f"Encharge {serial_number}",
            sw_version=str(encharge_inventory[self._serial_number].firmware_version),
            via_device=(DOMAIN, self.envoy_serial_num),
            serial_number=serial_number,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the Encharge binary_sensor."""
        encharge_inventory = self.data.encharge_inventory
        assert encharge_inventory is not None
        return self.entity_description.value_fn(encharge_inventory[self._serial_number])


class EnvoyEnpowerBinarySensorEntity(EnvoyBaseBinarySensorEntity):
    """Defines an Enpower binary_sensor entity."""

    entity_description: EnvoyEnpowerBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyEnpowerBinarySensorEntityDescription,
    ) -> None:
        """Init the Enpower base entity."""
        super().__init__(coordinator, description)
        enpower = self.data.enpower
        assert enpower is not None
        self._attr_unique_id = f"{enpower.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, enpower.serial_number)},
            manufacturer="Enphase",
            model="Enpower",
            name=f"Enpower {enpower.serial_number}",
            sw_version=str(enpower.firmware_version),
            via_device=(DOMAIN, self.envoy_serial_num),
            serial_number=enpower.serial_number,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the Enpower binary_sensor."""
        enpower = self.data.enpower
        assert enpower is not None
        return self.entity_description.value_fn(enpower)


class EnvoyCollarBinarySensorEntity(EnvoyBaseBinarySensorEntity):
    """Defines an IQ Meter Collar binary_sensor entity."""

    entity_description: EnvoyCollarBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyCollarBinarySensorEntityDescription,
    ) -> None:
        """Init the Collar base entity."""
        super().__init__(coordinator, description)
        collar_data = self.data.collar
        assert collar_data is not None
        self._attr_unique_id = f"{collar_data.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, collar_data.serial_number)},
            manufacturer="Enphase",
            model="IQ Meter Collar",
            name=f"Collar {collar_data.serial_number}",
            sw_version=str(collar_data.firmware_version),
            via_device=(DOMAIN, self.envoy_serial_num),
            serial_number=collar_data.serial_number,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the Collar binary_sensor."""
        collar_data = self.data.collar
        assert collar_data is not None
        return self.entity_description.value_fn(collar_data)


class EnvoyC6CCBinarySensorEntity(EnvoyBaseBinarySensorEntity):
    """Defines an C6 Combiner binary_sensor entity."""

    entity_description: EnvoyC6CCBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyC6CCBinarySensorEntityDescription,
    ) -> None:
        """Init the C6 Combiner base entity."""
        super().__init__(coordinator, description)
        c6cc_data = self.data.c6cc
        assert c6cc_data is not None
        self._attr_unique_id = f"{c6cc_data.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, c6cc_data.serial_number)},
            manufacturer="Enphase",
            model="C6 COMBINER CONTROLLER",
            name=f"C6 Combiner {c6cc_data.serial_number}",
            sw_version=str(c6cc_data.firmware_version),
            via_device=(DOMAIN, self.envoy_serial_num),
            serial_number=c6cc_data.serial_number,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the C6 Combiner binary_sensor."""
        c6cc_data = self.data.c6cc
        assert c6cc_data is not None
        return self.entity_description.value_fn(c6cc_data)
