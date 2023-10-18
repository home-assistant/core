"""ViCare helpers functions."""
import logging

from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError

from . import ViCareRequiredKeysMixin

_LOGGER = logging.getLogger(__name__)


def is_supported(
    vicare_device,
    entity_description: ViCareRequiredKeysMixin,
    name: str,
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
