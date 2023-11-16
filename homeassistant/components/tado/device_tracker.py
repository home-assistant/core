"""Support for Tado Smart device trackers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import DATA, DOMAIN, SIGNAL_TADO_MOBILE_DEVICE_UPDATE_RECEIVED

_LOGGER = logging.getLogger(__name__)


async def async_get_scanner(hass: HomeAssistant, config: ConfigType) -> None:
    """Configure the Tado device scanner."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml_import_device_tracker",
        breaks_in_ha_version="2024.5.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml_import_device_tracker",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tado device scannery entity."""
    _LOGGER.debug("Setting up Tado device scanner entity")
    tado = hass.data[DOMAIN][entry.entry_id][DATA]
    tracked: set = set()

    @callback
    def update_devices() -> None:
        """Update the values of the devices."""
        add_tracked_entities(hass, tado, async_add_entities, tracked)

    update_devices()

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_TADO_MOBILE_DEVICE_UPDATE_RECEIVED,
            update_devices,
        )
    )


@callback
def add_tracked_entities(
    hass: HomeAssistant,
    tado: Any,
    async_add_entities: AddEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new tracker entities from Tado."""
    _LOGGER.debug("Fetching Tado devices from API")
    new_tracked = []
    for device_key, device in tado.data["mobile_device"].items():
        if device_key in tracked:
            continue

        _LOGGER.debug(
            "Adding Tado device %s with deviceID %s", device["name"], device_key
        )
        new_tracked.append(TadoDeviceTrackerEntity(device_key, device["name"], tado))
        tracked.add(device_key)

    async_add_entities(new_tracked)


class TadoDeviceTrackerEntity(ScannerEntity):
    """A Tado Device Tracker entity."""

    _attr_should_poll = False

    def __init__(
        self,
        device_id: str,
        device_name: str,
        tado: Any,
    ) -> None:
        """Initialize a Tado Device Tracker entity."""
        super().__init__()
        self._device_id = device_id
        self._device_name = device_name
        self._tado = tado
        self._active = False
        self._mac_address = None

    @callback
    def update_state(self) -> None:
        """Update the Tado device."""
        _LOGGER.debug(
            "Updating Tado mobile device: %s (ID: %s)",
            self._device_name,
            self._device_id,
        )
        device = self._tado.data["mobile_device"][self._device_id]

        self._active = False
        if device.get("location") is not None and device["location"]["atHome"]:
            _LOGGER.debug("Tado device %s is at home", device["name"])
            self._active = True
        else:
            _LOGGER.debug("Tado device %s is not at home", device["name"])

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        _LOGGER.debug("Registering Tado device tracker entity")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_MOBILE_DEVICE_UPDATE_RECEIVED,
                self.update_state,
            )
        )

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device_name

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected and home."""
        return self._active

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS
