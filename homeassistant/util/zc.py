"""Zeroconf util functions."""

import logging

import zeroconf

_LOGGER = logging.getLogger(__name__)


def install_multiple_zeroconf_warning() -> None:
    """Wrap the Zeroconf class to warn if multiple instances are detected."""
    old_init = zeroconf.Zeroconf.__init__

    def new_init(self, *k, **kw) -> None:  # type: ignore
        if "from_hass" in kw:
            del kw["from_hass"]
        else:
            _LOGGER.warning(
                "Multiple Zeroconf instances detected. Please use the shared Zeroconf via homeassistant.components.zeroconf.async_get_instance()",
                stack_info=True,
            )
        old_init(self, *k, **kw)

    zeroconf.Zeroconf.__init__ = new_init
