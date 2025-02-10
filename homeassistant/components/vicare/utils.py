"""ViCare helpers functions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from typing import Any

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceComponent,
)
from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_HEATING_TYPE,
    DEFAULT_CACHE_DURATION,
    HEATING_TYPE_TO_CREATOR_METHOD,
    VICARE_TOKEN_FILENAME,
    HeatingType,
)
from .types import ViCareConfigEntry

_LOGGER = logging.getLogger(__name__)


def login(
    hass: HomeAssistant,
    entry_data: Mapping[str, Any],
    cache_duration=DEFAULT_CACHE_DURATION,
) -> PyViCare:
    """Login via PyVicare API."""
    vicare_api = PyViCare()
    vicare_api.setCacheDuration(cache_duration)
    vicare_api.initWithCredentials(
        entry_data[CONF_USERNAME],
        entry_data[CONF_PASSWORD],
        entry_data[CONF_CLIENT_ID],
        hass.config.path(STORAGE_DIR, VICARE_TOKEN_FILENAME),
    )
    return vicare_api


def get_device(
    entry: ViCareConfigEntry, device_config: PyViCareDeviceConfig
) -> PyViCareDevice:
    """Get device for device config."""
    return getattr(
        device_config,
        HEATING_TYPE_TO_CREATOR_METHOD[HeatingType(entry.data[CONF_HEATING_TYPE])],
    )()


def get_device_serial(device: PyViCareDevice) -> str | None:
    """Get device serial for device if supported."""
    try:
        return device.getSerial()
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("Device does not offer a 'device.serial' data point")
    except PyViCareRateLimitError as limit_exception:
        _LOGGER.debug("Vicare API rate limit exceeded: %s", limit_exception)
    except PyViCareInvalidDataError as invalid_data_exception:
        _LOGGER.debug("Invalid data from Vicare server: %s", invalid_data_exception)
    except requests.exceptions.ConnectionError:
        _LOGGER.debug("Unable to retrieve data from ViCare server")
    except ValueError:
        _LOGGER.debug("Unable to decode data from ViCare server")
    return None


def is_supported(
    name: str,
    getter: Callable[[PyViCareDevice], Any],
    vicare_device,
) -> bool:
    """Check if the PyViCare device supports the requested sensor."""
    try:
        getter(vicare_device)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("Feature not supported %s", name)
        return False
    except AttributeError as error:
        _LOGGER.debug("Feature not supported %s: %s", name, error)
        return False
    _LOGGER.debug("Found entity %s", name)
    return True


def get_burners(device: PyViCareDevice) -> list[PyViCareHeatingDeviceComponent]:
    """Return the list of burners."""
    try:
        return device.burners
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("No burners found")
    except AttributeError as error:
        _LOGGER.debug("No burners found: %s", error)
    return []


def get_circuits(device: PyViCareDevice) -> list[PyViCareHeatingDeviceComponent]:
    """Return the list of circuits."""
    try:
        return device.circuits
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("No circuits found")
    except AttributeError as error:
        _LOGGER.debug("No circuits found: %s", error)
    return []


def get_compressors(device: PyViCareDevice) -> list[PyViCareHeatingDeviceComponent]:
    """Return the list of compressors."""
    try:
        return device.compressors
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("No compressors found")
    except AttributeError as error:
        _LOGGER.debug("No compressors found: %s", error)
    return []


def filter_state(state: str) -> str | None:
    """Return the state if not 'nothing' or 'unknown'."""
    return None if state in ("nothing", "unknown") else state
