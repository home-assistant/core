"""Base class for Mikrotik routers entities."""

from yarl import URL

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import MikrotikConfigEntry, MikrotikDataUpdateCoordinator


class MikrotikBaseEntity(CoordinatorEntity[MikrotikDataUpdateCoordinator]):
    """Base class for all Mikrotik entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MikrotikDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description

        self._serial = coordinator.api.serial_number

    def _device_info(self, identifier: str, name: str | None) -> dr.DeviceInfo:
        """Return the device info of a Mikrotik device."""
        coordinator = self.coordinator
        return dr.DeviceInfo(
            configuration_url=URL.build(
                scheme="http",
                host=coordinator.host,
            ),
            identifiers={(DOMAIN, identifier)},
            manufacturer="Mikrotik",
            model=coordinator.model,
            name=name,
            sw_version=coordinator.firmware,
            serial_number=self._serial,
        )


class MikrotikEntity(MikrotikBaseEntity):
    """Base class for Mikrotik entities."""

    def __init__(
        self,
        coordinator: MikrotikDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, description)
        self._attr_device_info = self._device_info(self._serial, coordinator.hostname)
        self._attr_unique_id = f"{self._serial}_{description.key}"


class MikrotikDeviceEntity(MikrotikBaseEntity):
    """Base class for Mikrotik device entities."""

    def __init__(
        self,
        config_entry: MikrotikConfigEntry,
        coordinator: MikrotikDataUpdateCoordinator,
        description: EntityDescription,
        interface: dict,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, description)

        name = interface.get("name")
        ident = f"{slugify(interface.get('mac-address'))}_{name}"

        self._attr_device_info = self._device_info(ident, name)
        self._attr_device_info["via_device_id"] = dr.async_get_device_id_by_identifier(
            config_entry.runtime_data.hass,
            (DOMAIN, coordinator.api.serial_number),
            config_entry_id=config_entry.entry_id,
        )
        self._attr_unique_id = ident
        self._interface = interface
