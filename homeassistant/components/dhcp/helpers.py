"""The dhcp integration."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .models import DATA_DHCP, DHCPAddressData


@callback
def async_register_dhcp_callback_internal(
    hass: HomeAssistant,
    callback_: Callable[[dict[str, DHCPAddressData]], None],
) -> CALLBACK_TYPE:
    """Register a dhcp callback.

    For internal use only.
    This is not intended for use by integrations.
    """
    callbacks = hass.data[DATA_DHCP].callbacks
    callbacks.add(callback_)
    return partial(callbacks.remove, callback_)


@callback
def async_get_address_data_internal(
    hass: HomeAssistant,
) -> dict[str, DHCPAddressData]:
    """Get the address data.

    For internal use only.
    This is not intended for use by integrations.
    """
    return hass.data[DATA_DHCP].address_data
