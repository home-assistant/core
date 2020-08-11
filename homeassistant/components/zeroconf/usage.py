"""Zeroconf usage utility to warn about multiple instances."""

import zeroconf

from homeassistant.helpers.frame import warn_use


def install_multiple_zeroconf_warning() -> None:
    """Wrap the Zeroconf class to warn if multiple instances are detected."""

    zeroconf.Zeroconf.__init__ = warn_use(  # type: ignore
        zeroconf.Zeroconf.__init__,
        "created another Zeroconf instance. Please use the shared Zeroconf via homeassistant.components.zeroconf.async_get_instance()",
    )
