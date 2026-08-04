"""The Agent DVR integration."""

from dataclasses import dataclass
import logging
from urllib.parse import unquote, urlparse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import AgentDVRClient, AgentDVRError
from .const import DEFAULT_PORT, DEVICE_TYPE_CAMERA, DOMAIN, SERVER_URL
from .coordinator import AgentDVRDataUpdateCoordinator
from .services import async_setup_services
from .webrtc import AgentDVRWebRTCPool, AgentDVRWebRTCSession

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "ispyconnect.com"
DEFAULT_BRAND = "Agent DVR by ispyconnect.com"

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AgentDVRConfigEntry = ConfigEntry["AgentDVRData"]


@dataclass
class AgentDVRData:
    """Runtime data stored on the config entry."""

    client: AgentDVRClient
    coordinator: AgentDVRDataUpdateCoordinator
    webrtc_pool: AgentDVRWebRTCPool
    unique_id: str
    ptz_pulse_seconds: float = 0.4


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry to the current schema.

    Version 1 entries predate separate username/password fields: the old
    config flow only had a single `host` field, so the only way to reach
    a Protect-API-secured server was to type credentials directly into it
    as `user:pass@host`; a `server_url` built from that was stored
    alongside it. Version 2 splits that into clean host/port/username/
    password/ssl fields, since the WebRTC signaling client added in this
    version needs them separately (not as a pre-assembled URL).
    """
    if entry.version > 1:
        return True

    # The legacy schema always had a separate, already-clean CONF_PORT
    # field (never embedded in the host string), so there's no need to
    # extract it from the URL below - which matters because urlparse()
    # raises ValueError instead of returning None for a non-numeric port
    # component, and a not-fully-escaped legacy password could easily
    # produce one.
    source = entry.data.get(SERVER_URL) or entry.data[CONF_HOST]
    if "://" not in source:
        source = f"http://{source}"
    parsed = urlparse(source)

    # urlparse().username/.password return the still-percent-encoded
    # substrings (they only split the netloc, they don't decode it) - not
    # unquoting here would silently double-encode credentials that contain
    # special characters, breaking Basic Auth after migration.
    new_data = {
        CONF_HOST: parsed.hostname or entry.data[CONF_HOST],
        CONF_PORT: entry.data.get(CONF_PORT, DEFAULT_PORT),
        CONF_USERNAME: parsed.username and unquote(parsed.username),
        CONF_PASSWORD: parsed.password and unquote(parsed.password),
        CONF_SSL: parsed.scheme == "https",
    }
    hass.config_entries.async_update_entry(entry, data=new_data, version=2)
    _LOGGER.debug("Migrated agent_dvr config entry %s to version 2", entry.entry_id)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AgentDVRConfigEntry) -> bool:
    """Set up Agent DVR from a config entry."""
    session = async_get_clientsession(hass)
    client = AgentDVRClient(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        entry.data.get(CONF_SSL, False),
    )

    try:
        status = await client.get_status()
    except AgentDVRError as err:
        raise ConfigEntryNotReady from err

    unique_id = entry.unique_id or status.get("unique") or entry.entry_id

    coordinator = AgentDVRDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    webrtc_pool = AgentDVRWebRTCPool(
        lambda: AgentDVRWebRTCSession(
            async_get_clientsession(hass),
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data.get(CONF_USERNAME),
            entry.data.get(CONF_PASSWORD),
            entry.data.get(CONF_SSL, False),
        )
    )

    entry.runtime_data = AgentDVRData(
        client=client,
        coordinator=coordinator,
        webrtc_pool=webrtc_pool,
        unique_id=unique_id,
    )

    # Pre-create every device (the hub plus one per camera) with its final
    # name before forwarding to platforms. async_forward_entry_setups does
    # not guarantee platform setup order (camera in particular loads later
    # since it depends on the "camera"/"stream"/"http" components), so an
    # entity from e.g. select.py can easily be registered before camera.py
    # has had a chance to create its device. When that happens the device
    # exists but is nameless, and entities with has_entity_name=True and no
    # own name end up with a name-less/duplicate-prone entity_id that never
    # self-corrects once the camera device gets its name later.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, unique_id)},
        manufacturer="iSpyConnect",
        name=f"Agent {status.get('name', entry.title)}",
        model="Agent DVR",
        sw_version=status.get("version"),
    )
    server_name = status.get("name", "Agent DVR")
    for device in coordinator.data["devices"].values():
        if device["typeID"] != DEVICE_TYPE_CAMERA:
            continue
        camera_unique_id = f"{unique_id}_{device['typeID']}_{device['id']}"
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, camera_unique_id)},
            manufacturer="Agent",
            model="Camera",
            name=f"{server_name} {device['name']}",
            sw_version=status.get("version"),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AgentDVRConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.webrtc_pool.close()
    return unloaded
