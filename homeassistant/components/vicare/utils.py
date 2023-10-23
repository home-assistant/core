"""ViCare helpers functions."""
import logging

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError

from homeassistant.config_entries import ConfigEntry

from . import ViCareRequiredKeysMixin
from .const import CONF_HEATING_TYPE, HEATING_TYPE_TO_CREATOR_METHOD, HeatingType

_LOGGER = logging.getLogger(__name__)


def get_device(
    entry: ConfigEntry, device_config: PyViCareDeviceConfig
) -> PyViCareDevice:
    """Get device for device config."""
    return getattr(
        device_config,
        HEATING_TYPE_TO_CREATOR_METHOD[HeatingType(entry.data[CONF_HEATING_TYPE])],
    )()


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
