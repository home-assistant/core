"""SwitchBot via API integration."""

from asyncio import gather
from collections.abc import Awaitable, Callable
import contextlib
from dataclasses import dataclass, field
from logging import getLogger

from aiohttp import web
from switchbot_api import CannotConnect, Device, InvalidAuth, Remote, SwitchBotAPI

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, ENTRY_TITLE
from .coordinator import SwitchBotCoordinator

_LOGGER = getLogger(__name__)
PLATFORMS: list[Platform] = [
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

    buttons: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)
    climates: list[tuple[Remote, SwitchBotCoordinator]] = field(default_factory=list)
    switches: list[tuple[Device | Remote, SwitchBotCoordinator]] = field(
        default_factory=list
    )
    sensors: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)
    vacuums: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)
    locks: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)


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
    manageable_by_webhook: bool = False,
) -> SwitchBotCoordinator:
    """Instantiate coordinator and adds to list for gathering."""
    coordinator = coordinators_by_id.setdefault(
        device.device_id,
        SwitchBotCoordinator(hass, entry, api, device, manageable_by_webhook),
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
            hass, entry, api, device, coordinators_by_id, True
        )
        devices_data.vacuums.append((device, coordinator))

    if isinstance(device, Device) and device.device_type.startswith("Smart Lock"):
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.locks.append((device, coordinator))
        devices_data.sensors.append((device, coordinator))

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

    await _initialize_webhook(hass, entry, api, coordinators_by_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _initialize_webhook(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: SwitchBotAPI,
    coordinators_by_id: dict[str, SwitchBotCoordinator],
) -> None:
    """Initialize webhook if needed."""
    if any(
        coordinator.manageable_by_webhook()
        for coordinator in coordinators_by_id.values()
    ):
        # Need webhook because there coordinator updated by this
        if CONF_WEBHOOK_ID not in entry.data or entry.unique_id is None:
            new_data = entry.data.copy()
            unique_id = str(entry.data[CONF_API_TOKEN])
            if CONF_WEBHOOK_ID not in new_data:
                # create new id and new conf
                new_data[CONF_WEBHOOK_ID] = webhook.async_generate_id()

            hass.config_entries.async_update_entry(
                entry, data=new_data, unique_id=unique_id
            )

        # register webhook
        webhook_name = ENTRY_TITLE
        if entry.title != ENTRY_TITLE:
            webhook_name = f"{ENTRY_TITLE} {entry.title}"

        with contextlib.suppress(Exception):
            webhook.async_register(
                hass,
                DOMAIN,
                webhook_name,
                entry.data[CONF_WEBHOOK_ID],
                _create_handle_webhook(coordinators_by_id),
            )

        webhook_url = webhook.async_generate_url(
            hass,
            entry.data[CONF_WEBHOOK_ID],
        )

        # check if webhook is configured in switchbot cloud
        check_webhook_result = None
        with contextlib.suppress(Exception):
            check_webhook_result = await api.get_webook_configuration()

        actual_webhook_urls = (
            check_webhook_result["urls"]
            if check_webhook_result and "urls" in check_webhook_result
            else []
        )
        need_add_webhook = (
            len(actual_webhook_urls) == 0 or webhook_url not in actual_webhook_urls
        )
        need_clean_previous_webhook = (
            len(actual_webhook_urls) > 0 and webhook_url not in actual_webhook_urls
        )

        if need_clean_previous_webhook:
            # it seems is impossible to register multiple webhook.
            # So, if webhook already exists, we delete it
            await api.delete_webhook(actual_webhook_urls[0])
            _LOGGER.debug(
                "Deleted previous Switchbot cloud webhook url: %s",
                actual_webhook_urls[0],
            )

        if need_add_webhook:
            # call api for register webhookurl
            await api.setup_webhook(webhook_url)
            _LOGGER.debug("Registered Switchbot cloud webhook at hass: %s", webhook_url)

        for coordinator in coordinators_by_id.values():
            coordinator.webhook_subscription_listener(True)

        _LOGGER.debug("Registered Switchbot cloud webhook at: %s", webhook_url)


def _create_handle_webhook(
    coordinators_by_id: dict[str, SwitchBotCoordinator],
) -> Callable[[HomeAssistant, str, web.Request], Awaitable[None]]:
    """Create a webhook handler."""

    async def _internal_handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> None:
        """Handle webhook callback."""
        if not request.body_exists:
            _LOGGER.debug("Received invalid request from switchbot webhook")
            return

        data = await request.json()
        # Structure validation
        if (
            not isinstance(data, dict)
            or "eventType" not in data
            or data["eventType"] != "changeReport"
            or "eventVersion" not in data
            or data["eventVersion"] != "1"
            or "context" not in data
            or not isinstance(data["context"], dict)
            or "deviceType" not in data["context"]
            or "deviceMac" not in data["context"]
        ):
            _LOGGER.debug("Received invalid data from switchbot webhook %s", repr(data))
            return

        deviceMac = data["context"]["deviceMac"]

        if deviceMac not in coordinators_by_id:
            _LOGGER.error(
                "Received data for unknown entity from switchbot webhook: %s", data
            )
            return

        coordinators_by_id[deviceMac].async_set_updated_data(data["context"])

    return _internal_handle_webhook
