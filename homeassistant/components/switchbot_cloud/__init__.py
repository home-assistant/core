"""SwitchBot via API integration."""

from asyncio import gather
from collections.abc import Awaitable, Callable
import contextlib
from dataclasses import dataclass, field
from logging import getLogger
import secrets
from typing import Any

from aiohttp import web
from switchbot_api import CannotConnect, Device, InvalidAuth, Remote, SwitchBotAPI

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from .coordinator import SwitchBotCoordinator

_LOGGER = getLogger(__name__)
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]


@dataclass
class SwitchbotDevices:
    """Switchbot devices data."""

    climates: list[Remote] = field(default_factory=list)
    switches: list[Device | Remote] = field(default_factory=list)
    sensors: list[Device] = field(default_factory=list)
    vacuums: list[Device] = field(default_factory=list)


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
    update_by_webhook: bool = False,
) -> tuple[Device | Remote, SwitchBotCoordinator]:
    """Instantiate coordinator and adds to list for gathering."""
    coordinator = coordinators_by_id.setdefault(
        device.device_id, SwitchBotCoordinator(hass, api, device, update_by_webhook)
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
        if isinstance(device, Device) and device.device_type in [
            "Meter",
            "MeterPlus",
            "WoIOSensor",
        ]:
            devices_data.sensors.append(
                prepare_device(hass, api, device, coordinators_by_id)
            )
        if isinstance(device, Device) and device.device_type in ["K10+"]:
            devices_data.vacuums.append(
                prepare_device(hass, api, device, coordinators_by_id, True)
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

    if any(
        coordinator.update_by_webhook() for coordinator in coordinators_by_id.values()
    ):
        # Need webhook

        # Get/create config to store a unique id for this hass instance.
        store = Store[dict[str, Any]](
            hass, STORAGE_VERSION, STORAGE_KEY + "-" + config.entry_id
        )
        if not (persistent_config := await store.async_load()):
            # Create config
            persistent_config = {
                CONF_WEBHOOK_ID: secrets.token_hex(),
            }
            await store.async_save(persistent_config)

        # register webhook
        with contextlib.suppress(Exception):
            webhook.async_register(
                hass,
                DOMAIN,
                "SwitchBot Cloud",
                persistent_config[CONF_WEBHOOK_ID],
                create_handle_webhook(coordinators_by_id),
            )

        webhook_url = webhook.async_generate_url(
            hass, persistent_config[CONF_WEBHOOK_ID]
        )
        # check if webhook is configured
        check_webhook_result = None
        with contextlib.suppress(Exception):
            check_webhook_result = await api.get_webook_configuration()

        if (
            not check_webhook_result
            or "urls" not in check_webhook_result
            or webhook_url not in check_webhook_result["urls"]
        ):
            # call api for register webhookurl
            await api.setup_webhook(webhook_url)

    # ...
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def create_handle_webhook(
    coordinators_by_id: dict[str, SwitchBotCoordinator],
) -> Callable[[HomeAssistant, str, web.Request], Awaitable[None]]:
    """Create a webhook handler."""

    async def internal_handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> None:
        """Handle webhook callback."""
        data = await request.json()

        if not isinstance(data, dict):
            _LOGGER.error(
                "Received invalid data from switchbot webhook. Data needs to be a dictionary: %s",
                data,
            )
            return

        if "eventType" not in data or data["eventType"] != "changeReport":
            _LOGGER.error(
                'Received invalid data from switchbot webhook. Attribute eventType is missing or not equals to "changeReport": %s',
                data,
            )
            return

        if "eventVersion" not in data or data["eventVersion"] != "1":
            _LOGGER.error(
                'Received invalid data from switchbot webhook. Attribute eventVersion is missing or not equals to "1": %s',
                data,
            )
            return

        if "context" not in data or not isinstance(data["context"], dict):
            _LOGGER.error(
                "Received invalid data from switchbot webhook. Attribute context is missing or not instance of dict: %s",
                data,
            )
            return

        if "deviceType" not in data["context"] or "deviceMac" not in data["context"]:
            _LOGGER.error(
                "Received invalid data from switchbot webhook. Missing deviceType or deviceMac: %s",
                data,
            )
            return

        deviceMac = data["context"]["deviceMac"]

        if deviceMac not in coordinators_by_id:
            _LOGGER.error(
                "Received data for unknown entity from switchbot webhook: %s", data
            )
            return

        coordinators_by_id[deviceMac].async_set_updated_data(data["context"])

    return internal_handle_webhook
