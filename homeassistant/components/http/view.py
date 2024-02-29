"""Support for views."""
from __future__ import annotations

import logging

from homeassistant.helpers.http import (  # noqa: F401
    HomeAssistantView,
    request_handler_factory,
)

_LOGGER = logging.getLogger(__name__)
