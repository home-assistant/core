"""ViCare helpers functions."""
import logging

from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError

from . import ViCareRequiredKeysMixin

_LOGGER = logging.getLogger(__name__)


def is_supported(
    api,
    sensor: ViCareRequiredKeysMixin,
    name: str,
) -> bool:
    """Check if the PyViCare device supports the requested sensor."""
    try:
        sensor.value_getter(api)
        _LOGGER.info("Found entity %s", name)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("Feature not supported %s", name)
        return False
    except AttributeError as error:
        _LOGGER.error("Attribute Error %s: %s", name, error)
        return False

    return True
