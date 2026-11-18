"""The Hikvision integration."""

from dataclasses import dataclass, field
import logging
import uuid
from xml.etree.ElementTree import ParseError

from pyhik.constants import SENSOR_MAP
from pyhik.hikvision import HikCamera, VideoChannel, get_video_channels
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_RANDOM_ID, DOMAIN
from .identity import is_made_up_id, is_random_id_made_up, looks_made_up

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CAMERA, Platform.EVENT]


@dataclass
class HikvisionData:
    """Data class for Hikvision runtime data."""

    camera: HikCamera
    # What the entities and the device are registered under: stable, unlike the ID
    # pyHik makes up for a device whose own ID is too short.
    device_id: str
    # What pyHik puts in front of the events of the stream: the ID it gives now.
    stream_id: str
    device_name: str
    device_type: str
    host: str
    username: str
    password: str
    channels: dict[int, VideoChannel] = field(default_factory=dict)


type HikvisionConfigEntry = ConfigEntry[HikvisionData]


@callback
def _async_record_random_id(
    hass: HomeAssistant, entry: HikvisionConfigEntry, camera_id: object
) -> None:
    """Record where an older entry's ID came from, once the device settles it.

    The device answering with the entry's ID as its own shows it is its own; it
    answering with a random made-up one, for an entry whose ID has that form, shows
    pyHik made that one up too. Anything else settles nothing, and the form of the
    ID stays the guess.
    """
    if CONF_RANDOM_ID in entry.data or entry.unique_id is None:
        return
    if not isinstance(camera_id, uuid.UUID) and str(camera_id) == str(entry.unique_id):
        random_id = False
    elif is_random_id_made_up(camera_id) and looks_made_up(entry.unique_id):
        random_id = True
    else:
        return
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_RANDOM_ID: random_id}
    )


def _made_up_prefix(identifier: str, device_id: str) -> tuple[str, str] | None:
    """Split an identifier made with another made-up ID into that ID and the rest.

    The unique IDs and device identifiers start with the device's ID, then "_" and
    the rest, if any. A UUID has no "_" in it.
    """
    old_id, separator, rest = identifier.partition("_")
    if old_id == device_id or not looks_made_up(old_id):
        return None
    return old_id, separator + rest


@callback
def _async_adopt_made_up_identities(
    hass: HomeAssistant, entry: HikvisionConfigEntry, device_id: str
) -> None:
    """Move the devices and entities of earlier made-up IDs to the entry's own ID.

    Before the entry kept its ID, each setup registered them under the random ID
    pyHik made up on that connection, which differs from the one the entry was
    created with. The oldest of each is kept: it has the entity ID automations
    use. One the entry's ID already has is left as it is.
    """
    dev_reg = dr.async_get(hass)
    devices = sorted(
        dr.async_entries_for_config_entry(dev_reg, entry.entry_id),
        key=lambda device: device.created_at,
    )
    # The identifiers of the entry's devices, channel devices included.
    taken = {identifier for device in devices for identifier in device.identifiers}
    for device in devices:
        identifiers = set(device.identifiers)
        for domain, identifier in device.identifiers:
            if domain != DOMAIN or not (
                split := _made_up_prefix(identifier, device_id)
            ):
                continue
            new_identifier = (DOMAIN, device_id + split[1])
            if new_identifier not in taken:
                identifiers.discard((domain, identifier))
                identifiers.add(new_identifier)
                taken.add(new_identifier)
        if identifiers != device.identifiers:
            dev_reg.async_update_device(device.id, new_identifiers=identifiers)

    ent_reg = er.async_get(hass)
    for entity in sorted(
        er.async_entries_for_config_entry(ent_reg, entry.entry_id),
        key=lambda entity: entity.created_at,
    ):
        if not (split := _made_up_prefix(entity.unique_id, device_id)):
            continue
        new_unique_id = device_id + split[1]
        if ent_reg.async_get_entity_id(entity.domain, DOMAIN, new_unique_id) is None:
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)


async def async_setup_entry(hass: HomeAssistant, entry: HikvisionConfigEntry) -> None:
    """Set up Hikvision from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    ssl = entry.data[CONF_SSL]
    # Entries created before the option existed always verified the certificate
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)

    protocol = "https" if ssl else "http"
    url = f"{protocol}://{host}"

    try:
        camera = await hass.async_add_executor_job(
            HikCamera, url, port, username, password, verify_ssl
        )
    except requests.exceptions.RequestException as err:
        raise ConfigEntryNotReady(f"Unable to connect to {host}") from err

    if (camera_id := camera.get_id) is None:
        if camera.auth_failed:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            )
        raise ConfigEntryNotReady(f"Unable to get device ID from {host}")
    stream_id = str(camera_id)
    device_id = stream_id
    _async_record_random_id(hass, entry, camera_id)
    if isinstance(camera_id, uuid.UUID) and is_made_up_id(entry):
        # pyHik before 0.5.1 makes up a random ID for a device whose own ID is too
        # short, a new one at every connection. An entry created with such an ID
        # keeps it, so its device and entities stay the same. An entry with a real
        # or derived ID does not lend it: a camera that answers with a made-up ID
        # is not known to be the one it was created for.
        device_id = str(entry.unique_id)
        _async_adopt_made_up_identities(hass, entry, device_id)

    device_name = camera.get_name or host
    device_type = camera.get_type or "Camera"

    # For NVRs, fetch video channel information
    channels: dict[int, VideoChannel] = {}
    if device_type == "NVR":
        channel_list = await hass.async_add_executor_job(
            get_video_channels, host, port, username, password, ssl, verify_ssl
        )
        channels = {ch.id: ch for ch in channel_list}
        _LOGGER.debug("Found %d video channels", len(channels))

    entry.runtime_data = HikvisionData(
        camera=camera,
        device_id=device_id,
        stream_id=stream_id,
        device_name=device_name,
        device_type=device_type,
        host=host,
        username=username,
        password=password,
        channels=channels,
    )

    _LOGGER.debug(
        "Device %s (type=%s) initial event_states: %s",
        device_name,
        device_type,
        camera.current_event_states,
    )

    # For NVRs or devices with no detected events, try to fetch events from ISAPI
    # Use broader notification methods for NVRs since they often use 'record' etc.
    if device_type == "NVR" or not camera.current_event_states:
        nvr_notification_methods = {"center", "HTTP", "record", "email", "beep"}

        def fetch_and_inject_nvr_events() -> None:
            """Fetch and inject NVR events in a single executor job."""
            try:
                nvr_events = camera.get_event_triggers(nvr_notification_methods)
            except (requests.exceptions.RequestException, ParseError) as err:
                _LOGGER.warning("Unable to fetch event triggers from %s: %s", host, err)
                return

            _LOGGER.debug("NVR events fetched with extended methods: %s", nvr_events)
            if nvr_events:
                # Map raw event type names to friendly names using SENSOR_MAP
                mapped_events: dict[str, list[int]] = {}
                for event_type, channels in nvr_events.items():
                    event_key = event_type.lower()
                    # Skip videoloss - used as watchdog by pyhik, not a real sensor
                    if event_key == "videoloss":
                        continue
                    friendly_name = SENSOR_MAP.get(event_key)
                    if friendly_name is None:
                        _LOGGER.debug("Skipping unmapped event type: %s", event_type)
                        continue
                    if friendly_name in mapped_events:
                        mapped_events[friendly_name].extend(channels)
                    else:
                        mapped_events[friendly_name] = list(channels)
                _LOGGER.debug("Mapped NVR events: %s", mapped_events)
                if mapped_events:
                    camera.inject_events(mapped_events)
            else:
                _LOGGER.debug(
                    "No event triggers returned from %s. "
                    "Ensure events are configured on the device",
                    host,
                )

        await hass.async_add_executor_job(fetch_and_inject_nvr_events)

    # Start the event stream
    await hass.async_add_executor_job(camera.start_stream)

    async def _async_stop_stream(event: Event) -> None:
        await hass.async_add_executor_job(camera.disconnect)

    # pyHik's stream thread is non-daemonic and publishes straight into hass, so
    # it has to be joined before the event loop closes. Starting it yields, so
    # the stop event may already have been fired by the time we get here, and
    # listening for it now would never hear it.
    if hass.is_stopping:
        await hass.async_add_executor_job(camera.disconnect)
        raise ConfigEntryNotReady("Home Assistant is stopping")

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_stream)
    )

    # Register the main device before platforms that use via_device
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_id)},
        name=device_name,
        manufacturer="Hikvision",
        model=device_type,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: HikvisionConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    # Stop the event stream
    await hass.async_add_executor_job(entry.runtime_data.camera.disconnect)
