"""Samsung TV DMR/UPnP device handling."""

from collections.abc import Callable, Sequence

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpSessionRequester
from async_upnp_client.client import UpnpService, UpnpStateVariable
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import (
    UpnpActionResponseError,
    UpnpCommunicationError,
    UpnpConnectionError,
    UpnpError,
    UpnpResponseError,
    UpnpXmlContentError,
)
from async_upnp_client.profiles.dlna import DmrDevice
from async_upnp_client.utils import async_get_local_ip

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER


class SamsungTVDmrDevice:
    """Wrapper for the UPnP/DMR device lifecycle."""

    def __init__(
        self,
        hass: HomeAssistant,
        ssdp_rendering_control_location: str,
        host: str | None,
        on_event_callback: Callable[[], None],
    ) -> None:
        """Initialize the DMR device wrapper."""
        self._hass = hass
        self._ssdp_rendering_control_location = ssdp_rendering_control_location
        self._host = host
        self._on_event_callback = on_event_callback
        self._dmr_device: DmrDevice | None = None
        self._upnp_server: AiohttpNotifyServer | None = None

    @property
    def device(self) -> DmrDevice | None:
        """The DmrDevice instance, if started."""
        return self._dmr_device

    @property
    def is_subscribed(self) -> bool:
        """Whether the DMR device is subscribed to events."""
        return self._dmr_device is not None and self._dmr_device.is_subscribed

    @property
    def volume_level(self) -> float | None:
        """Current volume level from the DMR device."""
        if self._dmr_device is None:
            return None
        return self._dmr_device.volume_level

    @property
    def is_volume_muted(self) -> bool | None:
        """Whether volume is muted, from the DMR device."""
        if self._dmr_device is None:
            return None
        return self._dmr_device.is_volume_muted

    async def async_startup(self) -> None:
        """Create the UPnP device, start the notify server and subscribe to events."""
        assert self._ssdp_rendering_control_location is not None
        if self._dmr_device is None:
            session = async_get_clientsession(self._hass)
            upnp_requester = AiohttpSessionRequester(session)
            upnp_factory = UpnpFactory(upnp_requester, non_strict=True)
            try:
                upnp_device = await upnp_factory.async_create_device(
                    self._ssdp_rendering_control_location
                )
            except (UpnpConnectionError, UpnpResponseError, UpnpXmlContentError) as err:
                LOGGER.debug("Unable to create Upnp DMR device: %r", err, exc_info=True)
                return
            _, event_ip = await async_get_local_ip(
                self._ssdp_rendering_control_location, self._hass.loop
            )
            source = (event_ip or "0.0.0.0", 0)
            self._upnp_server = AiohttpNotifyServer(
                requester=upnp_requester,
                source=source,
                callback_url=None,
                loop=self._hass.loop,
            )
            await self._upnp_server.async_start_server()
            self._dmr_device = DmrDevice(upnp_device, self._upnp_server.event_handler)
            try:
                self._dmr_device.on_event = self._on_upnp_event
                await self._dmr_device.async_subscribe_services(auto_resubscribe=True)
            except UpnpResponseError as err:
                LOGGER.debug("Device rejected subscription: %r", err)
            except UpnpError as err:
                self._dmr_device.on_event = None
                self._dmr_device = None
                await self._upnp_server.async_stop_server()
                self._upnp_server = None
                LOGGER.debug("Error while subscribing during device connect: %r", err)
                raise

    async def async_resubscribe(self) -> None:
        """Re-subscribe to DMR events."""
        assert self._dmr_device
        try:
            await self._dmr_device.async_subscribe_services(auto_resubscribe=True)
        except UpnpCommunicationError as err:
            LOGGER.debug("Device rejected re-subscription: %r", err, exc_info=True)

    async def async_unsubscribe(self) -> None:
        """Unsubscribe from DMR events (TV turned off)."""
        if self._dmr_device is not None and self._dmr_device.is_subscribed:
            await self._dmr_device.async_unsubscribe_services()

    async def async_shutdown(self) -> None:
        """Shut down the DMR device and stop the UPnP server."""
        if (dmr_device := self._dmr_device) is not None:
            self._dmr_device = None
            dmr_device.on_event = None
            await dmr_device.async_unsubscribe_services()
        if (upnp_server := self._upnp_server) is not None:
            self._upnp_server = None
            await upnp_server.async_stop_server()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level via DMR."""
        if self._dmr_device is None:
            LOGGER.warning("Upnp services are not available on %s", self._host)
            return
        assert self._host
        try:
            await self._dmr_device.async_set_volume_level(volume)
        except UpnpActionResponseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_set_volume",
                translation_placeholders={
                    "error": repr(err),
                    "host": self._host,
                },
            ) from err

    @callback
    def _on_upnp_event(
        self,
        service: UpnpService,
        state_variables: Sequence[UpnpStateVariable],
    ) -> None:
        """State variable(s) changed, notify entity."""
        self._on_event_callback()
