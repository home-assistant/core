"""Base entity class for DROP entities."""

from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_DESC,
    CONF_DEVICE_NAME,
    CONF_DEVICE_OWNER_ID,
    CONF_DEVICE_TYPE,
    CONF_HUB_ID,
    DEV_HUB,
    DOMAIN,
)
from .coordinator import DROPDeviceDataUpdateCoordinator


class DROPEntity(CoordinatorEntity[DROPDeviceDataUpdateCoordinator]):
    """Representation of a DROP device entity."""

    _attr_has_entity_name = True

    def __init__(
        self, entity_type: str, coordinator: DROPDeviceDataUpdateCoordinator
    ) -> None:
        """Init DROP entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id is not None
        unique_id = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{unique_id}_{entity_type}"
        entry_data = coordinator.config_entry.data
        model: str = entry_data[CONF_DEVICE_DESC]
        if entry_data[CONF_DEVICE_TYPE] == DEV_HUB:
            model = f"Hub {entry_data[CONF_HUB_ID]}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Chandler Systems, Inc.",
            model=model,
            name=entry_data[CONF_DEVICE_NAME],
            identifiers={(DOMAIN, unique_id)},
        )
        if entry_data[CONF_DEVICE_TYPE] != DEV_HUB:
            # The owner hub lives in a separate config entry created independently
            # by MQTT discovery, so it may not exist yet. Link best-effort when
            # present; an identifier can match devices from several config entries
            # and we can't tell which is the owner hub, so link to the first.
            via_devices = dr.async_get(coordinator.hass).async_get_devices(
                identifiers={(DOMAIN, entry_data[CONF_DEVICE_OWNER_ID])}
            )
            if via_devices:
                self._attr_device_info["via_device_id"] = via_devices[0].id
