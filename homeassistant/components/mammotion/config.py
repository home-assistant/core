from homeassistant.helpers.storage import Store

from .const import DOMAIN


class MammotionConfigStore(Store):
    """A configuration store for Alexa."""

    _STORAGE_VERSION = 1
    _STORAGE_MINOR_VERSION = 1
    _STORAGE_KEY = DOMAIN
