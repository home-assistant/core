"""Support for AVM FRITZ!SmartHome devices."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pyfritzhome import FritzhomeDevice
from pyfritzhome.devicetypes.fritzhomeentitybase import FritzhomeEntityBase

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, UnitOfTemperature
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import FritzboxConfigEntry, FritzboxDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: FritzboxConfigEntry) -> bool:
    """Set up the AVM FRITZ!SmartHome platforms."""

    def _update_unique_id(entry: RegistryEntry) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        if (
            entry.unit_of_measurement == UnitOfTemperature.CELSIUS
            and "_temperature" not in entry.unique_id
        ):
            new_unique_id = f"{entry.unique_id}_temperature"
            LOGGER.info(
                "Migrating unique_id [%s] to [%s]", entry.unique_id, new_unique_id
            )
            return {"new_unique_id": new_unique_id}

        if entry.domain == BINARY_SENSOR_DOMAIN and "_" not in entry.unique_id:
            new_unique_id = f"{entry.unique_id}_alarm"
            LOGGER.info(
                "Migrating unique_id [%s] to [%s]", entry.unique_id, new_unique_id
            )
            return {"new_unique_id": new_unique_id}
        return None

    await async_migrate_entries(hass, entry.entry_id, _update_unique_id)

    coordinator = FritzboxDataUpdateCoordinator(hass, entry.entry_id)
    await coordinator.async_setup()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def logout_fritzbox(event: Event) -> None:
        """Close connections to this fritzbox."""
        coordinator.fritz.logout()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout_fritzbox)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FritzboxConfigEntry) -> bool:
    """Unloading the AVM FRITZ!SmartHome platforms."""
    await hass.async_add_executor_job(entry.runtime_data.fritz.logout)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: FritzboxConfigEntry, device: DeviceEntry
) -> bool:
    """Remove Fritzbox config entry from a device."""
    coordinator = entry.runtime_data

    for identifier in device.identifiers:
        if identifier[0] == DOMAIN and (
            identifier[1] in coordinator.data.devices
            or identifier[1] in coordinator.data.templates
        ):
            return False

    return True


class FritzBoxEntity(CoordinatorEntity[FritzboxDataUpdateCoordinator], ABC):
    """Basis FritzBox entity."""

    def __init__(
        self,
        coordinator: FritzboxDataUpdateCoordinator,
        ain: str,
        entity_description: EntityDescription | None = None,
    ) -> None:
        """Initialize the FritzBox entity."""
        super().__init__(coordinator)

        self.ain = ain
        if entity_description is not None:
            self._attr_has_entity_name = True
            self.entity_description = entity_description
            self._attr_unique_id = f"{ain}_{entity_description.key}"
        else:
            self._attr_name = self.data.name
            self._attr_unique_id = ain

    @property
    @abstractmethod
    def data(self) -> FritzhomeEntityBase:
        """Return data object from coordinator."""


class FritzBoxDeviceEntity(FritzBoxEntity):
    """Reflects FritzhomeDevice and uses its attributes to construct FritzBoxDeviceEntity."""

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.data.present

    @property
    def data(self) -> FritzhomeDevice:
        """Return device data object from coordinator."""
        return self.coordinator.data.devices[self.ain]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            name=self.data.name,
            identifiers={(DOMAIN, self.ain)},
            manufacturer=self.data.manufacturer,
            model=self.data.productname,
            sw_version=self.data.fw_version,
            configuration_url=self.coordinator.configuration_url,
        )
