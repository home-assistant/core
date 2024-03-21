"""Support for Tado Smart device trackers."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    DeviceScanner,
    SourceType,
    TrackerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from . import TadoConnector
from .const import CONF_HOME_ID, DATA, DOMAIN, SIGNAL_TADO_MOBILE_DEVICE_UPDATE_RECEIVED

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOME_ID): cv.string,
    }
)


async def async_get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> DeviceScanner | None:
    """Configure the Tado device scanner."""
    device_config = config["device_tracker"]
    import_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_USERNAME: device_config[CONF_USERNAME],
            CONF_PASSWORD: device_config[CONF_PASSWORD],
            CONF_HOME_ID: device_config.get(CONF_HOME_ID),
        },
    )

    translation_key = "deprecated_yaml_import_device_tracker"
    if import_result.get("type") == FlowResultType.ABORT:
        translation_key = "import_aborted"
        if import_result.get("reason") == "import_failed":
            translation_key = "import_failed"
        if import_result.get("reason") == "import_failed_invalid_auth":
            translation_key = "import_failed_invalid_auth"

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml_import_device_tracker",
        breaks_in_ha_version="2024.7.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
    )
    return None


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
            SIGNAL_TADO_MOBILE_DEVICE_UPDATE_RECEIVED.format(tado.home_id),
            update_devices,
        )
    )


@callback
def add_tracked_entities(
    hass: HomeAssistant,
    tado: TadoConnector,
    async_add_entities: AddEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new tracker entities from Tado."""
    _LOGGER.debug("Fetching Tado devices from API for (newly) tracked entities")
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


class TadoDeviceTrackerEntity(TrackerEntity):
    """A Tado Device Tracker entity."""

    _attr_should_poll = False
    _attr_available = False

    def __init__(
        self,
        device_id: str,
        device_name: str,
        tado: TadoConnector,
    ) -> None:
        """Initialize a Tado Device Tracker entity."""
        super().__init__()
        self._attr_unique_id = device_id
        self._device_id = device_id
        self._device_name = device_name
        self._tado = tado
        self._active = False
        self._latitude = None
        self._longitude = None

    @callback
    def update_state(self) -> None:
        """Update the Tado device."""
        _LOGGER.debug(
            "Updating Tado mobile device: %s (ID: %s)",
            self._device_name,
            self._device_id,
        )
        device = self._tado.data["mobile_device"][self._device_id]

        self._attr_available = False
        _LOGGER.debug(
            "Tado device %s has geoTracking state %s",
            device["name"],
            device["settings"]["geoTrackingEnabled"],
        )

        if device["settings"]["geoTrackingEnabled"] is False:
            return

        self._attr_available = True
        self._active = False
        if device.get("location") is not None and device["location"]["atHome"]:
            _LOGGER.debug("Tado device %s is at home", device["name"])
            self._active = True
        else:
            _LOGGER.debug("Tado device %s is not at home", device["name"])

    @callback
    def on_demand_update(self) -> None:
        """Update state on demand."""
        self.update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        _LOGGER.debug("Registering Tado device tracker entity")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_MOBILE_DEVICE_UPDATE_RECEIVED.format(self._tado.home_id),
                self.on_demand_update,
            )
        )

        self.update_state()

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device_name

    @property
    def location_name(self) -> str:
        """Return the state of the device."""
        return STATE_HOME if self._active else STATE_NOT_HOME

    @property
    def latitude(self) -> None:
        """Return latitude value of the device."""
        return None

    @property
    def longitude(self) -> None:
        """Return longitude value of the device."""
        return None

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS
