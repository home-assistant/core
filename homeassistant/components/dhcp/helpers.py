"""The dhcp integration."""

from collections.abc import Callable
from functools import partial

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import HOSTNAME, IP_ADDRESS
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


@callback
def async_discovered_service_info(hass: HomeAssistant) -> list[DhcpServiceInfo]:
    """Return the discovered DHCP devices."""
    return [
        DhcpServiceInfo(
            ip=data[IP_ADDRESS],
            hostname=data[HOSTNAME].lower(),
            macaddress=mac_address,
        )
        for mac_address, data in async_get_address_data_internal(hass).items()
    ]
