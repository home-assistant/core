"""AdGuard Home base entity."""

from homeassistant.config_entries import SOURCE_HASSIO
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AdGuardHomeCoordinator


class AdGuardHomeEntity[_CoordinatorT: AdGuardHomeCoordinator](
    CoordinatorEntity[_CoordinatorT]
):
    """Defines a base AdGuard Home entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: _CoordinatorT) -> None:
        """Initialize the AdGuard Home entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry

        host, port = entry.data[CONF_HOST], entry.data[CONF_PORT]
        if entry.source == SOURCE_HASSIO:
            config_url = "homeassistant://app/a0d7b954_adguard"
        elif entry.data[CONF_SSL]:
            config_url = f"https://{host}:{port}"
        else:
            config_url = f"http://{host}:{port}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="AdGuard Team",
            name="AdGuard Home",
            sw_version=str(entry.runtime_data.state.data.status.version),
            configuration_url=config_url,
        )
