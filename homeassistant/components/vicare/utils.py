"""ViCare helpers functions."""
import logging

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceComponent,
)
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError

from . import ViCareRequiredKeysMixin

_LOGGER = logging.getLogger(__name__)


def is_supported(
    name: str,
    entity_description: ViCareRequiredKeysMixin,
    vicare_device,
) -> bool:
    """Check if the PyViCare device supports the requested sensor."""
    try:
        entity_description.value_getter(vicare_device)
        _LOGGER.debug("Found entity %s", name)
        return True
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("Feature not supported %s", name)
    except AttributeError as error:
        _LOGGER.debug("Feature not supported %s: %s", name, error)
    return False


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
