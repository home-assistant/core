"""SwitchBot via API integration."""

from asyncio import gather
from dataclasses import dataclass, field
from logging import getLogger

from switchbot_api import CannotConnect, Device, InvalidAuth, Remote, SwitchBotAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import SwitchBotCoordinator

_LOGGER = getLogger(__name__)
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]


@dataclass
class SwitchbotDevices:
    """Switchbot devices data."""

    binary_sensors: list[Device] = field(default_factory=list)
    buttons: list[Device] = field(default_factory=list)
    climates: list[Remote] = field(default_factory=list)
    switches: list[Device | Remote] = field(default_factory=list)
    sensors: list[Device] = field(default_factory=list)
    vacuums: list[Device] = field(default_factory=list)
    locks: list[Device] = field(default_factory=list)


@dataclass
class SwitchbotCloudData:
    """Data to use in platforms."""

    api: SwitchBotAPI
    devices: SwitchbotDevices


async def coordinator_for_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: SwitchBotAPI,
    device: Device | Remote,
    coordinators_by_id: dict[str, SwitchBotCoordinator],
) -> SwitchBotCoordinator:
    """Instantiate coordinator and adds to list for gathering."""
    coordinator = coordinators_by_id.setdefault(
        device.device_id, SwitchBotCoordinator(hass, entry, api, device)
    )

    if coordinator.data is None:
        await coordinator.async_config_entry_first_refresh()

    return coordinator


async def make_switchbot_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: SwitchBotAPI,
    devices: list[Device | Remote],
    coordinators_by_id: dict[str, SwitchBotCoordinator],
) -> SwitchbotDevices:
    """Make SwitchBot devices."""
    devices_data = SwitchbotDevices()
    await gather(
        *[
            make_device_data(hass, entry, api, device, devices_data, coordinators_by_id)
            for device in devices
        ]
    )

    return devices_data


async def make_device_data(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: SwitchBotAPI,
    device: Device | Remote,
    devices_data: SwitchbotDevices,
    coordinators_by_id: dict[str, SwitchBotCoordinator],
) -> None:
    """Make device data."""
    if isinstance(device, Remote) and device.device_type.endswith("Air Conditioner"):
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.climates.append((device, coordinator))
    if (
        isinstance(device, Device)
        and (
            device.device_type.startswith("Plug")
            or device.device_type in ["Relay Switch 1PM", "Relay Switch 1"]
        )
    ) or isinstance(device, Remote):
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.switches.append((device, coordinator))

    if isinstance(device, Device) and device.device_type in [
        "Meter",
        "MeterPlus",
        "WoIOSensor",
        "Hub 2",
        "MeterPro",
        "MeterPro(CO2)",
        "Relay Switch 1PM",
        "Plug Mini (US)",
        "Plug Mini (JP)",
    ]:
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type in [
        "K10+",
        "K10+ Pro",
        "Robot Vacuum Cleaner S1",
        "Robot Vacuum Cleaner S1 Plus",
    ]:
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.vacuums.append((device, coordinator))

    if isinstance(device, Device) and device.device_type.startswith("Smart Lock"):
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.locks.append((device, coordinator))
        devices_data.sensors.append((device, coordinator))
        devices_data.binary_sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type in ["Bot"]:
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.sensors.append((device, coordinator))
        if coordinator.data is not None:
            if coordinator.data.get("deviceMode") == "pressMode":
                devices_data.buttons.append((device, coordinator))
            else:
                devices_data.switches.append((device, coordinator))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SwitchBot via API from a config entry."""
    token = entry.data[CONF_API_TOKEN]
    secret = entry.data[CONF_API_KEY]

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

    switchbot_devices = await make_switchbot_devices(
        hass, entry, api, devices, coordinators_by_id
    )
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = SwitchbotCloudData(
        api=api, devices=switchbot_devices
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
