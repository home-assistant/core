"""Zeroconf usage utility to warn about multiple instances."""

import logging

import zeroconf

from homeassistant.helpers.frame import (
    MissingIntegrationFrame,
    get_integration_frame,
    report_integration,
)

_LOGGER = logging.getLogger(__name__)


def install_multiple_zeroconf_catcher(hass_zc) -> None:
    """Wrap the Zeroconf class to return the shared instance if multiple instances are detected."""

    def new_zeroconf_new(self, *k, **kw):
        _report(
            "attempted to create another Zeroconf instance. Please use the shared Zeroconf via await homeassistant.components.zeroconf.async_get_instance(hass)",
        )
        return hass_zc

    def new_zeroconf_init(self, *k, **kw):
        return

    zeroconf.Zeroconf.__new__ = new_zeroconf_new
    zeroconf.Zeroconf.__init__ = new_zeroconf_init


def _report(what: str) -> None:
    """Report incorrect usage.

    Async friendly.
    """
    integration_frame = None

    try:
        integration_frame = get_integration_frame(exclude_integrations={"zeroconf"})
    except MissingIntegrationFrame:
        pass

    if not integration_frame:
        _LOGGER.warning(
            "Detected code that %s. Please report this issue.", what, stack_info=True
        )
        return

    report_integration(what, integration_frame)
