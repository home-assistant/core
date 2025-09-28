"""Helpers for switch entities."""

from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import DOMAIN, SwitchDeviceClass


@callback
def create_switch_device_class_select_selector() -> SelectSelector:
    """Create sensor device class select selector."""

    return SelectSelector(
        SelectSelectorConfig(
            options=[device_class.value for device_class in SwitchDeviceClass],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="device_class",
            translation_domain=DOMAIN,
            sort=True,
        )
    )
