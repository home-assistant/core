"""Zeroconf usage utility to warn about multiple instances."""

from typing import Any

import zeroconf

from homeassistant.helpers.frame import report

from .models import HaZeroconf


def install_multiple_zeroconf_catcher(hass_zc: HaZeroconf) -> None:
    """Wrap the Zeroconf class to return the shared instance if multiple instances are detected."""

    def new_zeroconf_new(self: zeroconf.Zeroconf, *k: Any, **kw: Any) -> HaZeroconf:
        report(
            "attempted to create another Zeroconf instance. Please use the shared Zeroconf via await homeassistant.components.zeroconf.async_get_instance(hass)",
            exclude_integrations={"zeroconf"},
            error_if_core=False,
        )
        return hass_zc

    def new_zeroconf_init(self: zeroconf.Zeroconf, *k: Any, **kw: Any) -> None:
        return

    zeroconf.Zeroconf.__new__ = new_zeroconf_new  # type: ignore
    zeroconf.Zeroconf.__init__ = new_zeroconf_init  # type: ignore
