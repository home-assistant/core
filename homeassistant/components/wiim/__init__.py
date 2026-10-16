"""The WiiM integration."""

from async_upnp_client.client import UpnpService, UpnpStateVariable
from wiim.controller import WiimController
from wiim.discovery import async_create_wiim_device
from wiim.exceptions import WiimDeviceException, WiimRequestException
from wiim.wiim_device import WiimDevice

from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DATA_WIIM,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SIGNAL_DEVICE_GENERAL_UPDATED,
    SIGNAL_DEVICE_RENDERING_CONTROL_UPDATED,
    UPNP_PORT,
    WiimConfigEntry,
)
from .models import WiimData
from .util import async_get_event_callback_host

DEFAULT_AVAILABILITY_POLLING_INTERVAL = 60


async def async_setup_entry(hass: HomeAssistant, entry: WiimConfigEntry) -> None:
    """Set up WiiM from a config entry.

    This method owns the device connect/disconnect lifecycle.
    """
    LOGGER.debug(
        "Setting up WiiM entry: %s (UDN: %s, Source: %s)",
        entry.title,
        entry.unique_id,
        entry.source,
    )

    # This integration maintains shared domain-level state because:
    # - Multiple config entries can be loaded simultaneously.
    # - All WiiM devices share a single WiimController instance
    #   to coordinate network communication and event handling.
    # - We also maintain a global entity_id -> UDN mapping
    #   used for cross-entity event routing.
    #
    # The domain data must therefore be initialized once and reused
    # across all config entries.
    session = async_get_clientsession(hass)

    if DATA_WIIM not in hass.data:
        hass.data[DATA_WIIM] = WiimData(controller=WiimController(session))

    wiim_domain_data = hass.data[DATA_WIIM]
    controller = wiim_domain_data.controller

    host = entry.data[CONF_HOST]
    upnp_location = f"http://{host}:{UPNP_PORT}/description.xml"

    try:
        local_host = await async_get_event_callback_host(hass, upnp_location)
    except HomeAssistantError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="callback_host_unavailable",
        ) from err

    try:
        wiim_device = await async_create_wiim_device(
            upnp_location,
            session,
            host=host,
            local_host=local_host,
            polling_interval=DEFAULT_AVAILABILITY_POLLING_INTERVAL,
        )
    except WiimRequestException as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="http_api_request_failed",
            translation_placeholders={"host": host},
        ) from err
    except WiimDeviceException as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_setup_failed",
            translation_placeholders={"host": host},
        ) from err

    await controller.add_device(wiim_device)

    entry.runtime_data = wiim_device

    @callback
    def _handle_general_update(device: WiimDevice) -> None:
        async_dispatcher_send(
            hass, SIGNAL_DEVICE_GENERAL_UPDATED.format(device.udn), device
        )
        if device.available and device.supports_http_api:
            entry.async_create_background_task(
                hass,
                device.ensure_subscriptions(),
                name=f"wiim_{device.udn}_ensure_subscriptions",
            )

    @callback
    def _handle_rendering_control_update(
        service: UpnpService, state_variables: list[UpnpStateVariable]
    ) -> None:
        async_dispatcher_send(
            hass,
            SIGNAL_DEVICE_RENDERING_CONTROL_UPDATED.format(wiim_device.udn),
            service,
            state_variables,
        )

    wiim_device.general_event_callback = _handle_general_update
    wiim_device.rendering_control_event_callback = _handle_rendering_control_update

    def _clear_device_event_callbacks() -> None:
        wiim_device.general_event_callback = None
        wiim_device.rendering_control_event_callback = None

    entry.async_on_unload(_clear_device_event_callbacks)
    LOGGER.info(
        "WiiM device %s (UDN: %s) linked to HASS. Name: '%s', HTTP: %s, UPnP Location: %s",
        entry.entry_id,
        wiim_device.udn,
        wiim_device.name,
        host,
        upnp_location or "N/A",
    )

    async def _async_shutdown_event_handler(event: Event) -> None:
        LOGGER.info(
            "Home Assistant stopping, disconnecting WiiM device: %s",
            wiim_device.name,
        )
        await wiim_device.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _async_shutdown_event_handler
        )
    )

    async def _unload_entry_cleanup() -> None:
        """Cleanup when unloading the config entry.

        Removes the device from the controller and disconnects it.
        """
        LOGGER.debug("Running unload cleanup for %s", wiim_device.name)
        await controller.remove_device(wiim_device.udn)
        await wiim_device.disconnect()

    entry.async_on_unload(_unload_entry_cleanup)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: WiimConfigEntry) -> None:
    """Unload a config entry."""
    LOGGER.info("Unloading WiiM entry: %s (UDN: %s)", entry.title, entry.unique_id)

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

    if not hass.config_entries.async_loaded_entries(DOMAIN):
        hass.data.pop(DATA_WIIM)
        LOGGER.info("Last WiiM entry unloaded, cleaning up domain data")
