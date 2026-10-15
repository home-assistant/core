"""Helper to test significant update state changes."""

from typing import Any

from homeassistant.core import HomeAssistant, callback

from .const import UpdateEntityStateAttribute


@callback
def async_check_significant_change(
    hass: HomeAssistant,
    old_state: str,
    old_attrs: dict,
    new_state: str,
    new_attrs: dict,
    **kwargs: Any,
) -> bool | None:
    """Test if state significantly changed."""
    if old_state != new_state:
        return True

    if old_attrs.get(UpdateEntityStateAttribute.INSTALLED_VERSION) != new_attrs.get(
        UpdateEntityStateAttribute.INSTALLED_VERSION
    ):
        return True

    if old_attrs.get(UpdateEntityStateAttribute.LATEST_VERSION) != new_attrs.get(
        UpdateEntityStateAttribute.LATEST_VERSION
    ):
        return True

    return False
