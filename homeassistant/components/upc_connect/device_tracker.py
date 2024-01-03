"""Support for UPC ConnectBox router."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    ScannerEntity,
    SourceType,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import UpcConnectDevice, UpcConnectDeviceScanner, signal_device_update
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_IP = "192.168.0.1"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_IP): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up UPC connect from a config entry."""

    upc_connect_tracker = hass.data[DOMAIN][entry.entry_id]

    @callback
    def device_new(mac_address):
        """Signal a new device."""
        device = upc_connect_tracker.devices.tracked[mac_address]
        _LOGGER.debug("Device new: mac_address=%s, device=%s", mac_address, device)
        async_add_entities(
            [UpcConnectTrackerEntity(upc_connect_tracker, mac_address, True)]
        )

    @callback
    def device_missing(mac_address):
        """Signal a missing device."""
        device = upc_connect_tracker.devices.tracked[mac_address]
        _LOGGER.debug("Device missing: mac_address=%s, device=%s", mac_address, device)
        async_add_entities(
            [UpcConnectTrackerEntity(upc_connect_tracker, mac_address, False)]
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, upc_connect_tracker.signal_device_new, device_new
        )
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, upc_connect_tracker.signal_device_missing, device_missing
        )
    )


async def async_get_scanner(hass: HomeAssistant, config: ConfigType) -> None:
    """Validate the configuration and return a UPC connect scanner."""
    # _LOGGER.debug("async_get_scanner: config=%s", config)

    validated_config = config[DEVICE_TRACKER_DOMAIN]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: validated_config[CONF_HOST],
                CONF_PASSWORD: validated_config[CONF_PASSWORD],
            },
        )
    )

    _LOGGER.warning(
        "Your UPC Tracker configuration has been imported into the UI, "
        "please remove it from configuration.yaml. "
    )


class UpcConnectTrackerEntity(ScannerEntity):
    """An UPC connect Tracker entity."""

    _attr_should_poll = False

    def __init__(
        self,
        upc_connect_tracker: UpcConnectDeviceScanner,
        mac_address: str,
        active: bool,
    ) -> None:
        """Initialize an UPC connect entity."""
        # _LOGGER.debug("UpcConnectTrackerEntity::__init__")

        self._mac_address = mac_address
        self._upc_connect_tracker = upc_connect_tracker
        self._tracked = self._upc_connect_tracker.devices.tracked
        self._active = active

    @property
    def _device(self) -> UpcConnectDevice:
        """Get latest device state."""
        return self._tracked[self._mac_address]

    @property
    def is_connected(self) -> bool:
        """Return device status."""
        return self._active

    @property
    def name(self) -> str:
        """Return device name."""
        return self._device.name

    @property
    def unique_id(self) -> str:
        """Return device unique id."""
        return self._mac_address

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self._device.ip_address

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac_address

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self._device.hostname

    @property
    def source_type(self) -> SourceType:
        """Return tracker source type."""
        return SourceType.ROUTER

    @property
    def icon(self) -> str:
        """Return device icon."""
        return "mdi:lan-connect" if self._active else "mdi:lan-disconnect"

    @callback
    def async_process_update(self, online: bool) -> None:
        """Update device."""
        self._active = online

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes."""
        return {
            "last_time_reachable": self._device.last_update.isoformat(
                timespec="seconds"
            )
        }

    @callback
    def async_on_demand_update(self, online: bool) -> None:
        """Update state."""
        self.async_process_update(online)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_device_update(self._mac_address),
                self.async_on_demand_update,
            )
        )
