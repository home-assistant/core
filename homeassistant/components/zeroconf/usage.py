"""Zeroconf usage utility to warn about multiple instances."""

from contextlib import suppress
import logging
from typing import Any

import zeroconf
from zeroconf import Zeroconf

from homeassistant.helpers.frame import (
    MissingIntegrationFrame,
    get_integration_frame,
    report_integration,
)

_LOGGER = logging.getLogger(__name__)


def install_multiple_zeroconf_catcher(hass_zc: Zeroconf) -> None:
    """Wrap the Zeroconf class to return the shared instance if multiple instances are detected."""

    def new_zeroconf_new(self: zeroconf.Zeroconf, *k: Any, **kw: Any) -> Zeroconf:
        _report(
            "attempted to create another Zeroconf instance. Please use the shared Zeroconf via await homeassistant.components.zeroconf.async_get_instance(hass)",
        )
        return hass_zc

    def new_zeroconf_init(self: zeroconf.Zeroconf, *k: Any, **kw: Any) -> None:
        return

    zeroconf.Zeroconf.__new__ = new_zeroconf_new  # type: ignore
    zeroconf.Zeroconf.__init__ = new_zeroconf_init  # type: ignore


def _report(what: str) -> None:
    """Report incorrect usage.

    Async friendly.
    """
    integration_frame = None

    with suppress(MissingIntegrationFrame):
        integration_frame = get_integration_frame(exclude_integrations={"zeroconf"})

    if not integration_frame:
        _LOGGER.warning(
            "Detected code that %s; Please report this issue", what, stack_info=True
        )
        return

    report_integration(what, integration_frame)
