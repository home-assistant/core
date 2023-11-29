"""The SwitchBot via API integration."""
from asyncio import gather
from dataclasses import dataclass, field
from logging import getLogger

from switchbot_api import CannotConnect, Device, InvalidAuth, Remote, SwitchBotAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import SwitchBotCoordinator

_LOGGER = getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SWITCH]


@dataclass
class SwitchbotDevices:
    """Switchbot devices data."""

    climates: list[Remote] = field(default_factory=list)
    switches: list[Device | Remote] = field(default_factory=list)


@dataclass
class SwitchbotCloudData:
    """Data to use in platforms."""

    api: SwitchBotAPI
    devices: SwitchbotDevices


@callback
def prepare_device(
    hass: HomeAssistant,
    api: SwitchBotAPI,
    device: Device | Remote,
    coordinators_by_id: dict[str, SwitchBotCoordinator],
) -> tuple[Device | Remote, SwitchBotCoordinator]:
    """Instantiate coordinator and adds to list for gathering."""
    coordinator = coordinators_by_id.setdefault(
        device.device_id, SwitchBotCoordinator(hass, api, device)
    )
    return (device, coordinator)


@callback
def make_device_data(
    hass: HomeAssistant,
    api: SwitchBotAPI,
    devices: list[Device | Remote],
    coordinators_by_id: dict[str, SwitchBotCoordinator],
) -> SwitchbotDevices:
    """Make device data."""
    devices_data = SwitchbotDevices()
    for device in devices:
        if isinstance(device, Remote) and device.device_type.endswith(
            "Air Conditioner"
        ):
            devices_data.climates.append(
                prepare_device(hass, api, device, coordinators_by_id)
            )
        if (
            isinstance(device, Device)
            and device.device_type.startswith("Plug")
            or isinstance(device, Remote)
        ):
            devices_data.switches.append(
                prepare_device(hass, api, device, coordinators_by_id)
            )
    return devices_data


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
    coordinators_by_id: dict[str, SwitchBotCoordinator] = {}
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config.entry_id] = SwitchbotCloudData(
        api=api, devices=make_device_data(hass, api, devices, coordinators_by_id)
    )
    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)
    await gather(
        *[coordinator.async_refresh() for coordinator in coordinators_by_id.values()]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
