"""Base entities for the Sunsynk integration."""

from sunsynk.inverter import Inverter

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SunsynkDataUpdateCoordinator


def inverter_device_info(inverter: Inverter) -> DeviceInfo:
    """Return the device info of an inverter."""
    name = f"Inverter {inverter.sn}"
    if inverter.alias and inverter.alias != inverter.sn:
        name = inverter.alias
    return DeviceInfo(
        identifiers={(DOMAIN, inverter.sn)},
        name=name,
        manufacturer="Sunsynk",
        model=inverter.model or None,
        serial_number=inverter.sn,
        sw_version=inverter.version.soft_ver if inverter.version else None,
    )


class SunsynkInverterEntity(CoordinatorEntity[SunsynkDataUpdateCoordinator]):
    """An entity of a Sunsynk inverter."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SunsynkDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.inverter.sn}_{description.key}"
        self._attr_device_info = inverter_device_info(coordinator.inverter)


class SunsynkBatteryEntity(CoordinatorEntity[SunsynkDataUpdateCoordinator]):
    """An entity of the battery of a Sunsynk inverter."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SunsynkDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        serial_number = coordinator.inverter.sn
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{serial_number}_battery")},
            name=f"Battery {serial_number}",
            manufacturer="Sunsynk",
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, serial_number),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
        )
