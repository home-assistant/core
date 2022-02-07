"""Support for Cybro PLC binary sensor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

# from homeassistant.components.cybro.sensor import CybroSensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AREA_SYSTEM,
    DEVICE_DESCRIPTION,
    DOMAIN,
    MANUFACTURER,
    MANUFACTURER_URL,
)
from .coordinator import CybroDataUpdateCoordinator
from .models import CybroEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    variable_name: str = "",
) -> None:
    """Set up a Cybro binary sensor based on a config entry."""
    coordinator: CybroDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if variable_name == "":
        var_prefix = f"c{coordinator.cybro.nad}."
        dev_info = DeviceInfo(
            # entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, var_prefix)},
            manufacturer=MANUFACTURER,
            # name=f"Light {key}",
            default_name=f"{var_prefix} Diagnosis",
            suggested_area=AREA_SYSTEM,
            model=f"{DEVICE_DESCRIPTION} controller",
            configuration_url=MANUFACTURER_URL,
        )
        async_add_entities(
            [
                CybroUpdateBinarySensor(
                    coordinator,
                    var_prefix + "scan_overrun",
                    attr_entity_category=EntityCategory.DIAGNOSTIC,
                    attr_device_class=BinarySensorDeviceClass.PROBLEM,
                    dev_info=dev_info,
                ),
                CybroUpdateBinarySensor(
                    coordinator,
                    var_prefix + "retentive_fail",
                    attr_entity_category=EntityCategory.DIAGNOSTIC,
                    attr_device_class=BinarySensorDeviceClass.PROBLEM,
                    dev_info=dev_info,
                ),
                CybroUpdateBinarySensor(
                    coordinator,
                    var_prefix + "general_error",
                    attr_entity_category=EntityCategory.DIAGNOSTIC,
                    attr_device_class=BinarySensorDeviceClass.PROBLEM,
                    dev_info=dev_info,
                ),
            ]
        )
        return
    async_add_entities(
        [
            CybroUpdateBinarySensor(
                coordinator,
                variable_name,
            )
        ]
    )


class CybroUpdateBinarySensor(CybroEntity, BinarySensorEntity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(
        self,
        coordinator: CybroDataUpdateCoordinator,
        var_name: str = "",
        attr_entity_category: EntityCategory = None,
        attr_device_class: BinarySensorDeviceClass = None,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator=coordinator)
        if var_name == "":
            return
        self._attr_name = var_name
        self._attr_unique_id = var_name
        self._attr_entity_category = attr_entity_category
        self._attr_device_class = attr_device_class
        self._attr_device_info = dev_info
        # LOGGER.debug(self.coordinator.data)
        # LOGGER.debug(self._attr_unique_id)
        # LOGGER.debug(self.coordinator)
        # LOGGER.debug(coordinator.cybro)
        coordinator.data.add_var(self._attr_unique_id, var_type=0)

    @property
    def is_on(self) -> bool | None:
        """Return entity state."""
        if self._attr_unique_id in self.coordinator.data.vars:
            self._attr_available = True
            return self.coordinator.data.vars[self._attr_unique_id].value == "1"
        self._attr_available = False
        return None
