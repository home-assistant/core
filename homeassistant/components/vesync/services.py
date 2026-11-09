"""Support for VeSync Services."""

from pyvesync.utils.errors import VeSyncError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, SERVICE_UPDATE_DEVS, VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Handle for services."""

    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_DEVS, async_new_device_discovery
    )


async def async_new_device_discovery(call: ServiceCall) -> None:
    """Discover and add new devices."""

    entries = call.hass.config_entries.async_entries(DOMAIN)
    config_entry: VesyncConfigEntry | None = entries[0] if entries else None

    if not config_entry:
        raise ServiceValidationError("Entry not found")
    if config_entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError("Entry not loaded")
    manager = config_entry.runtime_data.manager
    known_devices = list(manager.devices)
    try:
        await manager.get_devices()
    except VeSyncError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="api_response_error"
        ) from err
    new_devices = [device for device in manager.devices if device not in known_devices]

    if new_devices:
        async_dispatcher_send(call.hass, VS_DISCOVERY.format(VS_DEVICES), new_devices)
