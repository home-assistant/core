"""ViCare helpers functions."""
from collections.abc import Mapping
import logging
from typing import Any

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceComponent,
)
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError

from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR

from . import ViCareRequiredKeysMixin
from .const import DEFAULT_SCAN_INTERVAL, VICARE_TOKEN_FILENAME

_LOGGER = logging.getLogger(__name__)


def login(hass: HomeAssistant, entry_data: Mapping[str, Any]) -> PyViCare:
    """Login via PyVicare API."""
    api = PyViCare()
    api.setCacheDuration(DEFAULT_SCAN_INTERVAL)
    api.initWithCredentials(
        entry_data[CONF_USERNAME],
        entry_data[CONF_PASSWORD],
        entry_data[CONF_CLIENT_ID],
        hass.config.path(STORAGE_DIR, VICARE_TOKEN_FILENAME),
    )
    return api


def is_supported(
    name: str,
    entity_description: ViCareRequiredKeysMixin,
    vicare_device,
) -> bool:
    """Check if the PyViCare device supports the requested sensor."""
    try:
        entity_description.value_getter(vicare_device)
        _LOGGER.debug("Found entity %s", name)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("Feature not supported %s", name)
        return False
    except AttributeError as error:
        _LOGGER.debug("Attribute Error %s: %s", name, error)
        return False
    return True


def get_device_config_list(
    hass: HomeAssistant, entry_data: Mapping[str, Any]
) -> list[PyViCareDeviceConfig]:
    """Return the list of device configs."""
    api = login(hass, entry_data)
    for device in api.devices:
        _LOGGER.info(
            "Found device: %s (online: %s)", device.getModel(), str(device.isOnline())
        )
    return api.devices


def get_burners(device: PyViCareDevice) -> list[PyViCareHeatingDeviceComponent]:
    """Return the list of burners."""
    try:
        return device.burners
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("No burners found")
    return []


def get_circuits(device: PyViCareDevice) -> list[PyViCareHeatingDeviceComponent]:
    """Return the list of circuits."""
    try:
        return device.circuits
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("No circuits found")
    return []


def get_compressors(device: PyViCareDevice) -> list[PyViCareHeatingDeviceComponent]:
    """Return the list of compressors."""
    try:
        return device.compressors
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("No compressors found")
    return []


def get_serial(device_config: PyViCareDeviceConfig) -> str:
    """Return the serial number for a device config."""
    # we cannot always use device_config.getConfig().serial as it returns the gateway serial for all connected devices
    if device_config.getModel() == "Heatbox1":
        return device_config.getConfig().serial

    # we cannot always use device.getSerial() either as there is a different API endpoint used for gateways that does not provide the serial (yet)
    return device_config.asAutoDetectDevice().getSerial()
