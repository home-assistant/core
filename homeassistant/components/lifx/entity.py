"""Support for LIFX entities."""

from typing import override

from lifx import mac_candidates_for_serial

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LIFXConfigEntry, LIFXState, LIFXUpdateCoordinator


@callback
def async_repair_device_registry(
    hass: HomeAssistant,
    entry: LIFXConfigEntry,
    state: LIFXState,
) -> None:
    """Replace a derived MAC connection with the one the device reports.

    Before lifx-async the MAC was derived from the serial for firmware 3.70 and
    above, which wrongly offset firmware 4.x, so an upgraded installation can
    hold either candidate. Both are dropped for the address the device reports.
    """
    registry = dr.async_get(hass)
    identifier = (DOMAIN, state.serial)
    if not (
        device := registry.async_get_device_by_identifier(identifier, entry.entry_id)
    ):
        return

    derived = {
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(candidate))
        for candidate in mac_candidates_for_serial(state.serial)
    }
    connections = (device.connections - derived) | {
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(state.mac_address))
    }
    if connections != device.connections:
        registry.async_update_device(device.id, new_connections=connections)


class LIFXEntity(CoordinatorEntity[LIFXUpdateCoordinator]):
    """Representation of a LIFX entity with a coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        if description is not None:
            self.entity_description = description
        self._attr_unique_id = (
            coordinator.serial_number
            if description is None
            else f"{coordinator.serial_number}_{description.key}"
        )
        state = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, state.serial)},
            connections={(dr.CONNECTION_NETWORK_MAC, state.mac_address)},
            manufacturer="LIFX",
            name=state.label,
            serial_number=state.serial,
            model=state.model,
            model_id=(
                str(version.product)
                if (version := coordinator.device.version) is not None
                else None
            ),
            sw_version=(
                f"{state.host_firmware.version_major}."
                f"{state.host_firmware.version_minor}"
            ),
            suggested_area=state.group.label,
        )

    @callback
    def _async_update_attrs(self) -> None:
        """Update the attributes that track coordinator data."""

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()
