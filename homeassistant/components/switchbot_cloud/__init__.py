"""The SwitchBot via API integration."""
from asyncio import gather
from dataclasses import dataclass
from logging import getLogger

from switchbot_api import Device, Remote, SwitchBotAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SwitchBotCoordinator

_LOGGER = getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SWITCH]


@dataclass
class Data:
    """Data to use in platforms."""

    api: SwitchBotAPI
    switches: list[Device | Remote]


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up SwitchBot via API from a config entry."""
    token = config.data[CONF_API_TOKEN]
    secret = config.data[CONF_API_KEY]


    api = SwitchBotAPI(token=token, secret=secret)
    devices = await api.list_devices()
    _LOGGER.debug("Devices: %s", devices)
    devices_and_coordinators = [
        (device, SwitchBotCoordinator(hass, api, device)) for device in devices
    ]
    hass.data.setdefault(DOMAIN, {})
    data = Data(
        api=api,
        switches=[
            (device, coordinator)
            for device, coordinator in devices_and_coordinators
            if isinstance(device, Device)
            and device.device_type.startswith("Plug")
            or isinstance(device, Remote)
        ],
    )
    hass.data[DOMAIN][config.entry_id] = data
    _LOGGER.debug("Switches: %s", data.switches)
    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)
    await gather(
        *[coordinator.async_refresh() for _, coordinator in devices_and_coordinators]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
