"""Support for OpenWrt (ubus) routers as a device tracker."""

from typing import TYPE_CHECKING, override

import probatio

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Event,
    HomeAssistant,
    callback,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DHCP_SOFTWARE, DEFAULT_DHCP_SOFTWARE, DHCP_SOFTWARES, DOMAIN
from .coordinator import UbusConfigEntry, UbusDataUpdateCoordinator

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
        probatio.Required(CONF_USERNAME): cv.string,
        probatio.Optional(
            CONF_DHCP_SOFTWARE, default=DEFAULT_DHCP_SOFTWARE
        ): probatio.In(DHCP_SOFTWARES),
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import the legacy YAML device tracker into a config entry."""
    import_data = {
        CONF_HOST: config[CONF_HOST],
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_DHCP_SOFTWARE: config[CONF_DHCP_SOFTWARE],
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data
    )

    if result["type"] is FlowResultType.ABORT and result["reason"] in (
        "cannot_connect",
        "invalid_auth",
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"yaml_import_{result['reason']}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key=f"yaml_import_{result['reason']}",
            translation_placeholders={"host": config[CONF_HOST]},
        )
        return False

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.5.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "OpenWrt (ubus)",
        },
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the device tracker for a ubus config entry."""
    coordinator = config_entry.runtime_data
    tracked: set[str] = set()

    device_registry = dr.async_get(hass)

    @callback
    def _async_update_devices() -> None:
        new_macs = [mac for mac in coordinator.data if mac not in tracked]
        tracked.update(new_macs)
        if new_macs:
            async_add_entities(UbusScannerEntity(coordinator, mac) for mac in new_macs)
        # Rename here, as trackers are disabled by default and get no updates.
        for mac, name in coordinator.data.items():
            if (
                name
                and (
                    device_entry := device_registry.async_get_device_by_connection(
                        (dr.CONNECTION_NETWORK_MAC, mac), config_entry.entry_id
                    )
                )
                and device_entry.name != name
            ):
                device_registry.async_update_device(device_entry.id, name=name)

    @callback
    def _async_device_removed(
        event: Event[dr.EventDeviceRegistryUpdatedData],
    ) -> None:
        """Track a client again if it reconnects after its device was removed."""
        if TYPE_CHECKING:
            assert event.data["action"] == "remove"
        connections = set(event.data["device"]["connections"])
        tracked.difference_update(
            [
                mac
                for mac in tracked
                if (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac)) in connections
            ]
        )

    @callback
    def _is_own_device_removed(event_data: dr.EventDeviceRegistryUpdatedData) -> bool:
        return (
            event_data["action"] == "remove"
            and event_data["device"]["config_entry_id"] == config_entry.entry_id
        )

    config_entry.async_on_unload(coordinator.async_add_listener(_async_update_devices))
    config_entry.async_on_unload(
        hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
            _async_device_removed,
            event_filter=_is_own_device_removed,
        )
    )
    _async_update_devices()


class UbusScannerEntity(CoordinatorEntity[UbusDataUpdateCoordinator], ScannerEntity):
    """Representation of a device connected to an OpenWrt router."""

    def __init__(self, coordinator: UbusDataUpdateCoordinator, mac: str) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self._mac = mac
        connection = (dr.CONNECTION_NETWORK_MAC, mac)
        if name := coordinator.data.get(mac):
            self._attr_device_info = dr.DeviceInfo(connections={connection}, name=name)
        elif dr.async_get(coordinator.hass).async_get_device_by_connection(
            connection, coordinator.config_entry.entry_id
        ):
            # Without a hostname, keep the name of an existing device.
            self._attr_device_info = dr.DeviceInfo(connections={connection})
        else:
            self._attr_device_info = dr.DeviceInfo(connections={connection}, name=mac)

    @property
    @override
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    @property
    @override
    def is_connected(self) -> bool:
        """Return whether the device is connected to the router."""
        return self._mac in self.coordinator.data

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        return self.coordinator.data.get(self._mac)
