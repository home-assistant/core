"""Home Assistant representation of an UPnP/IGD."""

from __future__ import annotations

from datetime import datetime
from functools import partial
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpSessionRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.const import AddressTupleVXType
from async_upnp_client.exceptions import UpnpConnectionError
from async_upnp_client.profiles.igd import IgdDevice, IgdStateItem
from async_upnp_client.utils import async_get_local_ip
from getmac import get_mac_address

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    KIBIBYTES_PER_SEC_RECEIVED,
    KIBIBYTES_PER_SEC_SENT,
    LOGGER as _LOGGER,
    PACKETS_PER_SEC_RECEIVED,
    PACKETS_PER_SEC_SENT,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    PORT_MAPPING_NUMBER_OF_ENTRIES_IPV4,
    ROUTER_IP,
    ROUTER_UPTIME,
    TIMESTAMP,
    WAN_STATUS,
)

TYPE_STATE_ITEM_MAPPING = {
    BYTES_RECEIVED: IgdStateItem.BYTES_RECEIVED,
    BYTES_SENT: IgdStateItem.BYTES_SENT,
    KIBIBYTES_PER_SEC_RECEIVED: IgdStateItem.KIBIBYTES_PER_SEC_RECEIVED,
    KIBIBYTES_PER_SEC_SENT: IgdStateItem.KIBIBYTES_PER_SEC_SENT,
    PACKETS_PER_SEC_RECEIVED: IgdStateItem.PACKETS_PER_SEC_RECEIVED,
    PACKETS_PER_SEC_SENT: IgdStateItem.PACKETS_PER_SEC_SENT,
    PACKETS_RECEIVED: IgdStateItem.PACKETS_RECEIVED,
    PACKETS_SENT: IgdStateItem.PACKETS_SENT,
    ROUTER_IP: IgdStateItem.EXTERNAL_IP_ADDRESS,
    ROUTER_UPTIME: IgdStateItem.UPTIME,
    WAN_STATUS: IgdStateItem.CONNECTION_STATUS,
    PORT_MAPPING_NUMBER_OF_ENTRIES_IPV4: IgdStateItem.PORT_MAPPING_NUMBER_OF_ENTRIES,
}


def get_preferred_location(locations: set[str]) -> str:
    """Get the preferred location (an IPv4 location) from a set of locations."""
    # Prefer IPv4 over IPv6.
    for location in locations:
        if location.startswith(("http://[", "https://[")):
            continue

        return location

    # Fallback to any.
    for location in locations:
        return location

    raise ValueError("No location found")


async def async_get_mac_address_from_host(hass: HomeAssistant, host: str) -> str | None:
    """Get mac address from host."""
    ip_addr = ip_address(host)
    if ip_addr.version == 4:
        mac_address = await hass.async_add_executor_job(
            partial(get_mac_address, ip=host)
        )
    else:
        mac_address = await hass.async_add_executor_job(
            partial(get_mac_address, ip6=host)
        )
    return mac_address


async def async_create_device(
    hass: HomeAssistant, location: str, force_poll: bool
) -> Device:
    """Create UPnP/IGD device."""
    session = async_get_clientsession(hass, verify_ssl=False)
    requester = AiohttpSessionRequester(session, with_sleep=True, timeout=20)

    # Create UPnP device.
    factory = UpnpFactory(requester, non_strict=True)
    upnp_device = await factory.async_create_device(location)

    # Create notify server.
    _, local_ip = await async_get_local_ip(location)
    source: AddressTupleVXType = (local_ip, 0)
    notify_server = AiohttpNotifyServer(
        requester=requester,
        source=source,
    )
    await notify_server.async_start_server()
    _LOGGER.debug("Started event handler at %s", notify_server.callback_url)

    # Create profile wrapper.
    igd_device = IgdDevice(upnp_device, notify_server.event_handler)
    return Device(hass, igd_device, force_poll)


class Device:
    """Home Assistant representation of a UPnP/IGD device."""

    def __init__(
        self, hass: HomeAssistant, igd_device: IgdDevice, force_poll: bool
    ) -> None:
        """Initialize UPnP/IGD device."""
        self.hass = hass
        self._igd_device = igd_device
        self._force_poll = force_poll

        self.coordinator: (
            DataUpdateCoordinator[dict[str, str | datetime | int | float | None]] | None
        ) = None
        self.original_udn: str | None = None

    async def async_get_mac_address(self) -> str | None:
        """Get mac address."""
        if not self.host:
            return None

        return await async_get_mac_address_from_host(self.hass, self.host)

    @property
    def udn(self) -> str:
        """Get the UDN."""
        return self._igd_device.udn

    @property
    def name(self) -> str:
        """Get the name."""
        return self._igd_device.name

    @property
    def manufacturer(self) -> str:
        """Get the manufacturer."""
        return self._igd_device.manufacturer

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._igd_device.model_name

    @property
    def device_type(self) -> str:
        """Get the device type."""
        return self._igd_device.device_type

    @property
    def usn(self) -> str:
        """Get the USN."""
        return f"{self.udn}::{self.device_type}"

    @property
    def unique_id(self) -> str:
        """Get the unique id."""
        return self.usn

    @property
    def host(self) -> str | None:
        """Get the hostname."""
        parsed = urlparse(self.device_url)
        return parsed.hostname

    @property
    def device_url(self) -> str:
        """Get the device_url of the device."""
        return self._igd_device.device.device_url

    @property
    def serial_number(self) -> str | None:
        """Get the serial number."""
        return self._igd_device.device.serial_number

    def __str__(self) -> str:
        """Get string representation."""
        return f"IGD Device: {self.name}/{self.udn}::{self.device_type}"

    @property
    def force_poll(self) -> bool:
        """Get force_poll."""
        return self._force_poll

    async def async_set_force_poll(self, force_poll: bool) -> None:
        """Set force_poll, and (un)subscribe if needed."""
        self._force_poll = force_poll

        if self._force_poll:
            # No need for subscriptions, as eventing will never be used.
            await self.async_unsubscribe_services()
        elif not self._force_poll and not self._igd_device.is_subscribed:
            await self.async_subscribe_services()

    async def async_subscribe_services(self) -> None:
        """Subscribe to services."""
        try:
            await self._igd_device.async_subscribe_services(auto_resubscribe=True)
        except UpnpConnectionError as ex:
            _LOGGER.debug(
                "Error subscribing to services, falling back to forced polling: %s", ex
            )
            await self.async_set_force_poll(True)

    async def async_unsubscribe_services(self) -> None:
        """Unsubscribe from services."""
        await self._igd_device.async_unsubscribe_services()

    async def async_get_data(
        self, entity_description_keys: list[str] | None
    ) -> dict[str, str | datetime | int | float | None]:
        """Get all data from device."""
        if not entity_description_keys:
            igd_state_items = None
        else:
            igd_state_items = {
                TYPE_STATE_ITEM_MAPPING[key] for key in entity_description_keys
            }

        _LOGGER.debug(
            "Getting data for device: %s, state_items: %s, force_poll: %s",
            self,
            igd_state_items,
            self._force_poll,
        )
        igd_state = await self._igd_device.async_get_traffic_and_status_data(
            igd_state_items, force_poll=self._force_poll
        )

        def get_value(value: Any) -> Any:
            if value is None or isinstance(value, BaseException):
                return None

            return value

        return {
            TIMESTAMP: igd_state.timestamp,
            BYTES_RECEIVED: get_value(igd_state.bytes_received),
            BYTES_SENT: get_value(igd_state.bytes_sent),
            PACKETS_RECEIVED: get_value(igd_state.packets_received),
            PACKETS_SENT: get_value(igd_state.packets_sent),
            WAN_STATUS: get_value(igd_state.connection_status),
            ROUTER_UPTIME: get_value(igd_state.uptime),
            ROUTER_IP: get_value(igd_state.external_ip_address),
            KIBIBYTES_PER_SEC_RECEIVED: igd_state.kibibytes_per_sec_received,
            KIBIBYTES_PER_SEC_SENT: igd_state.kibibytes_per_sec_sent,
            PACKETS_PER_SEC_RECEIVED: igd_state.packets_per_sec_received,
            PACKETS_PER_SEC_SENT: igd_state.packets_per_sec_sent,
            PORT_MAPPING_NUMBER_OF_ENTRIES_IPV4: get_value(
                igd_state.port_mapping_number_of_entries
            ),
        }
