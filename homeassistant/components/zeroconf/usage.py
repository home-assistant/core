"""Zeroconf usage utility to warn about multiple instances."""

from typing import Any

import zeroconf

from homeassistant.helpers.frame import ReportBehavior, report_usage

from .models import HaZeroconf


def install_multiple_zeroconf_catcher(hass_zc: HaZeroconf) -> None:
    """Wrap the Zeroconf class to return the shared instance.

    Only if if multiple instances are detected.
    """

    def new_zeroconf_new(self: zeroconf.Zeroconf, *k: Any, **kw: Any) -> HaZeroconf:
        report_usage(
            (
                "attempted to create another Zeroconf instance. Please use the shared"
                " Zeroconf via await"
                " homeassistant.components.zeroconf.async_get_instance(hass)"
            ),
            exclude_integrations={"zeroconf"},
            core_behavior=ReportBehavior.LOG,
        )
        return hass_zc

    def new_zeroconf_init(self: zeroconf.Zeroconf, *k: Any, **kw: Any) -> None:
        return

    zeroconf.Zeroconf.__new__ = new_zeroconf_new  # type: ignore[assignment]
    zeroconf.Zeroconf.__init__ = new_zeroconf_init  # type: ignore[method-assign]
