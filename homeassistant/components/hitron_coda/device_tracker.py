"""Track devices connected to a Hitron CODA router."""

import logging
from typing import override

import probatio

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
    ScannerEntity,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TYPE, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import CannotConnect, DeviceData, HitronCodaClient, InvalidAuth
from .const import DEFAULT_TYPE, DOMAIN
from .coordinator import HitronCodaConfigEntry, HitronCodaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(CONF_USERNAME): cv.string,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
        probatio.Optional(CONF_TYPE, default=DEFAULT_TYPE): cv.string,
    }
)


async def async_get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> HitronCodaDeviceScanner | None:
    """Keep existing YAML trackers working until the user migrates them."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2027.5.0",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    router = config[DEVICE_TRACKER_DOMAIN]
    client = HitronCodaClient(
        router[CONF_HOST],
        router[CONF_USERNAME],
        router[CONF_PASSWORD],
        router[CONF_TYPE],
    )
    try:
        devices = await hass.async_add_executor_job(client.get_devices)
    except (CannotConnect, InvalidAuth) as err:
        _LOGGER.error("Unable to set up the Hitron CODA scanner: %s", err)
        return None
    return HitronCodaDeviceScanner(client, devices)


class HitronCodaDeviceScanner(DeviceScanner):
    """Update legacy trackers while their YAML configuration is still present."""

    def __init__(self, client: HitronCodaClient, devices: DeviceData) -> None:
        """Initialize the scanner with the first successful response."""
        self._client = client
        self._devices = devices

    @override
    def scan_devices(self) -> list[str]:
        """Return the last successful device list when the router is unavailable."""
        try:
            self._devices = self._client.get_devices()
        except (CannotConnect, InvalidAuth) as err:
            _LOGGER.warning("Unable to update the Hitron CODA scanner: %s", err)
        return list(self._devices)

    @override
    def get_device_name(self, device: str) -> str | None:
        """Return the hostname last reported by the router."""
        return self._devices.get(device)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HitronCodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device trackers for the router."""
    coordinator = entry.runtime_data
    registry = er.async_get(hass)
    registered = {
        format_mac(entity.unique_id).upper(): entity.original_name
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity.domain == DEVICE_TRACKER_DOMAIN
    }
    tracked = set(registered)
    async_add_entities(
        HitronCodaScannerEntity(coordinator, mac, hostname)
        for mac, hostname in registered.items()
    )

    @callback
    def async_add_devices() -> None:
        """Add devices first seen in a successful update."""
        new_macs = coordinator.data.keys() - tracked
        tracked.update(new_macs)
        async_add_entities(
            HitronCodaScannerEntity(coordinator, mac) for mac in sorted(new_macs)
        )

    entry.async_on_unload(coordinator.async_add_listener(async_add_devices))
    async_add_devices()


class HitronCodaScannerEntity(
    CoordinatorEntity[HitronCodaDataUpdateCoordinator], ScannerEntity
):
    """Represent a client seen on the router's network."""

    def __init__(
        self,
        coordinator: HitronCodaDataUpdateCoordinator,
        mac: str,
        hostname: str | None = None,
    ) -> None:
        """Initialize a client using its stable MAC address."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_mac_address = format_mac(mac)
        self._attr_hostname = coordinator.data.get(mac, hostname)
        self._attr_name = self._attr_hostname or self._attr_mac_address

    @property
    @override
    def is_connected(self) -> bool:
        """Return whether the client was seen in the latest successful scan."""
        return self._mac in self.coordinator.data

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update client names, retaining them while a client is disconnected."""
        if self._mac in self.coordinator.data:
            self._attr_hostname = self.coordinator.data[self._mac]
            self._attr_name = self._attr_hostname or self._attr_mac_address
        super()._handle_coordinator_update()
