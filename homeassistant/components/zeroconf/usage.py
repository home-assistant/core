"""Zeroconf usage utility to warn about multiple instances."""

import zeroconf

from homeassistant.helpers.frame import report


def install_multiple_zeroconf_catcher(zc) -> None:
    """Wrap the Zeroconf class to return the shared instance if multiple instances are detected."""

    def new_zeroconf_new(self, *k, **kw) -> zeroconf.Zeroconf:  # type: ignore
        report(
            "attempted to create another Zeroconf instance. Please use the shared Zeroconf via await homeassistant.components.zeroconf.async_get_instance(hass)",
            exclude_integrations={"zeroconf"},
        )
        return zc

    zeroconf.Zeroconf.__new__ = new_zeroconf_new
