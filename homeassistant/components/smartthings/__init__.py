"""Support for SmartThings Cloud."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, cast

from aiohttp import ClientError
from pysmartthings import (
    Attribute,
    Capability,
    Device,
    DeviceEvent,
    Scene,
    SmartThings,
    SmartThingsAuthenticationFailedError,
    SmartThingsSinkError,
    Status,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .const import (
    CONF_INSTALLED_APP_ID,
    CONF_LOCATION_ID,
    CONF_SUBSCRIPTION_ID,
    DOMAIN,
    EVENT_BUTTON,
    MAIN,
    OLD_DATA,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class SmartThingsData:
    """Define an object to hold SmartThings data."""

    devices: dict[str, FullDevice]
    scenes: dict[str, Scene]
    rooms: dict[str, str]
    client: SmartThings


@dataclass
class FullDevice:
    """Define an object to hold device data."""

    device: Device
    status: dict[str, dict[Capability | str, dict[Attribute | str, Status]]]


type SmartThingsConfigEntry = ConfigEntry[SmartThingsData]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.EVENT,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VALVE,
]


async def async_setup_entry(hass: HomeAssistant, entry: SmartThingsConfigEntry) -> bool:
    """Initialize config entry which represents an installed SmartApp."""
    # The oauth smartthings entry will have a token, older ones are version 3
    # after migration but still require reauthentication
    if CONF_TOKEN not in entry.data:
        raise ConfigEntryAuthFailed("Config entry missing token")
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except ClientError as err:
        raise ConfigEntryNotReady from err

    client = SmartThings(session=async_get_clientsession(hass))

    async def _refresh_token() -> str:
        await session.async_ensure_token_valid()
        token = session.token[CONF_ACCESS_TOKEN]
        if TYPE_CHECKING:
            assert isinstance(token, str)
        return token

    client.refresh_token_function = _refresh_token

    def _handle_max_connections() -> None:
        _LOGGER.debug("We hit the limit of max connections")
        hass.config_entries.async_schedule_reload(entry.entry_id)

    client.max_connections_reached_callback = _handle_max_connections

    def _handle_new_subscription_identifier(identifier: str | None) -> None:
        """Handle a new subscription identifier."""
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_SUBSCRIPTION_ID: identifier,
            },
        )
        if identifier is not None:
            _LOGGER.debug("Updating subscription ID to %s", identifier)
        else:
            _LOGGER.debug("Removing subscription ID")

    client.new_subscription_id_callback = _handle_new_subscription_identifier

    if (old_identifier := entry.data.get(CONF_SUBSCRIPTION_ID)) is not None:
        _LOGGER.debug("Trying to delete old subscription %s", old_identifier)
        await client.delete_subscription(old_identifier)

    _LOGGER.debug("Trying to create a new subscription")
    try:
        subscription = await client.create_subscription(
            entry.data[CONF_LOCATION_ID],
            entry.data[CONF_TOKEN][CONF_INSTALLED_APP_ID],
        )
    except SmartThingsSinkError as err:
        _LOGGER.exception("Couldn't create a new subscription")
        raise ConfigEntryNotReady from err
    subscription_id = subscription.subscription_id
    _handle_new_subscription_identifier(subscription_id)

    entry.async_create_background_task(
        hass,
        client.subscribe(
            entry.data[CONF_LOCATION_ID],
            entry.data[CONF_TOKEN][CONF_INSTALLED_APP_ID],
            subscription,
        ),
        "smartthings_socket",
    )

    device_status: dict[str, FullDevice] = {}
    try:
        rooms = {
            room.room_id: room.name
            for room in await client.get_rooms(location_id=entry.data[CONF_LOCATION_ID])
        }
        devices = await client.get_devices()
        for device in devices:
            status = process_status(await client.get_device_status(device.device_id))
            device_status[device.device_id] = FullDevice(device=device, status=status)
    except SmartThingsAuthenticationFailedError as err:
        raise ConfigEntryAuthFailed from err

    device_registry = dr.async_get(hass)
    for dev in device_status.values():
        for component in dev.device.components:
            if component.id == MAIN and Capability.BRIDGE in component.capabilities:
                assert dev.device.hub
                device_registry.async_get_or_create(
                    config_entry_id=entry.entry_id,
                    identifiers={(DOMAIN, dev.device.device_id)},
                    connections=(
                        {(dr.CONNECTION_NETWORK_MAC, dev.device.hub.mac_address)}
                        if dev.device.hub.mac_address
                        else set()
                    ),
                    name=dev.device.label,
                    sw_version=dev.device.hub.firmware_version,
                    model=dev.device.hub.hardware_type,
                    suggested_area=(
                        rooms.get(dev.device.room_id) if dev.device.room_id else None
                    ),
                )
    scenes = {
        scene.scene_id: scene
        for scene in await client.get_scenes(location_id=entry.data[CONF_LOCATION_ID])
    }

    entry.runtime_data = SmartThingsData(
        devices={
            device_id: device
            for device_id, device in device_status.items()
            if MAIN in device.status
        },
        client=client,
        scenes=scenes,
        rooms=rooms,
    )

    def handle_button_press(event: DeviceEvent) -> None:
        """Handle a button press."""
        if (
            event.capability is Capability.BUTTON
            and event.attribute is Attribute.BUTTON
        ):
            hass.bus.async_fire(
                EVENT_BUTTON,
                {
                    "component_id": event.component_id,
                    "device_id": event.device_id,
                    "location_id": event.location_id,
                    "value": event.value,
                    "name": entry.runtime_data.devices[event.device_id].device.label,
                    "data": event.data,
                },
            )

    entry.async_on_unload(
        client.add_unspecified_device_event_listener(handle_button_press)
    )

    async def _handle_shutdown(_: Event) -> None:
        """Handle shutdown."""
        await client.delete_subscription(subscription_id)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _handle_shutdown)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    for device_entry in device_entries:
        device_id = next(
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        )
        if device_id in device_status:
            continue
        device_registry.async_update_device(
            device_entry.id, remove_config_entry_id=entry.entry_id
        )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SmartThingsConfigEntry
) -> bool:
    """Unload a config entry."""
    client = entry.runtime_data.client
    if (subscription_id := entry.data.get(CONF_SUBSCRIPTION_ID)) is not None:
        await client.delete_subscription(subscription_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle config entry migration."""

    if entry.version < 3:
        # We keep the old data around, so we can use that to clean up the webhook in the future
        hass.config_entries.async_update_entry(
            entry, version=3, data={OLD_DATA: dict(entry.data)}
        )

    return True


KEEP_CAPABILITY_QUIRK: dict[
    Capability | str, Callable[[dict[Attribute | str, Status]], bool]
] = {
    Capability.DRYER_OPERATING_STATE: (
        lambda status: status[Attribute.SUPPORTED_MACHINE_STATES].value is not None
    ),
    Capability.WASHER_OPERATING_STATE: (
        lambda status: status[Attribute.SUPPORTED_MACHINE_STATES].value is not None
    ),
    Capability.DEMAND_RESPONSE_LOAD_CONTROL: lambda _: True,
}


def process_status(
    status: dict[str, dict[Capability | str, dict[Attribute | str, Status]]],
) -> dict[str, dict[Capability | str, dict[Attribute | str, Status]]]:
    """Remove disabled capabilities from status."""
    if (main_component := status.get(MAIN)) is None:
        return status
    if (
        disabled_capabilities_capability := main_component.get(
            Capability.CUSTOM_DISABLED_CAPABILITIES
        )
    ) is not None:
        disabled_capabilities = cast(
            list[Capability | str],
            disabled_capabilities_capability[Attribute.DISABLED_CAPABILITIES].value,
        )
        if disabled_capabilities is not None:
            for capability in disabled_capabilities:
                if capability in main_component and (
                    capability not in KEEP_CAPABILITY_QUIRK
                    or not KEEP_CAPABILITY_QUIRK[capability](main_component[capability])
                ):
                    del main_component[capability]
    return status
