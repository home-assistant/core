"""The SwitchBot via API integration."""
from asyncio import gather
from dataclasses import dataclass
from logging import getLogger

from switchbot_api import CannotConnect, Device, InvalidAuth, Remote, SwitchBotAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import SwitchBotCoordinator

_LOGGER = getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SWITCH]


@dataclass
class SwitchbotDevices:
    """Switchbot devices data."""

    switches: list[Device | Remote]


@dataclass
class SwitchbotCloudData:
    """Data to use in platforms."""

    api: SwitchBotAPI
    devices: SwitchbotDevices


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up SwitchBot via API from a config entry."""
    token = config.data[CONF_API_TOKEN]
    secret = config.data[CONF_API_KEY]

    api = SwitchBotAPI(token=token, secret=secret)
    try:
        devices = await api.list_devices()
    except InvalidAuth as ex:
        _LOGGER.error(
            "Invalid authentication while connecting to SwitchBot API: %s", ex
        )
        return False
    except CannotConnect as ex:
        raise ConfigEntryNotReady from ex
    _LOGGER.debug("Devices: %s", devices)
    devices_and_coordinators = [
        (device, SwitchBotCoordinator(hass, api, device)) for device in devices
    ]
    hass.data.setdefault(DOMAIN, {})
    data = SwitchbotCloudData(
        api=api,
        devices=SwitchbotDevices(
            switches=[
                (device, coordinator)
                for device, coordinator in devices_and_coordinators
                if isinstance(device, Device)
                and device.device_type.startswith("Plug")
                or isinstance(device, Remote)
            ],
        ),
    )
    hass.data[DOMAIN][config.entry_id] = data
    _LOGGER.debug("Switches: %s", data.devices.switches)
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
