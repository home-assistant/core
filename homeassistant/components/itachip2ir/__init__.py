"""Global Caché iTach IP2IR integration."""

from dataclasses import dataclass
import logging

from pyitach import (
    ItachClient,
    ItachConnectionError,
    ItachError,
    async_get_ir_capability,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DISCOVERY,
    DOMAIN,
    ISSUE_CANNOT_CONNECT,
    ISSUE_INVALID_CONFIG,
    ISSUE_NO_IR_PORTS,
)
from .discovery import ItachDiscovery
from .repairs import async_create_repair_issue, async_delete_repair_issue

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.INFRARED]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class ItachRuntimeData:
    """Runtime data for one iTach config entry."""

    host: str
    port: int
    device_id: str
    ir_module: int
    ir_ports: int
    ir_enabled_ports: list[int]
    ir_connector_modes: dict[str, str]
    client: ItachClient


type ItachConfigEntry = ConfigEntry[ItachRuntimeData]


def _discovery_disabled(hass: HomeAssistant) -> bool:
    """Return true when UDP discovery is disabled by tests."""
    return bool(hass.data.get("itachip2ir_disable_discovery", False))


def _issue_id(issue: str, entry: ConfigEntry) -> str:
    """Return a per-entry repair issue id."""
    return f"{issue}_{entry.entry_id}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the iTach integration."""
    hass.data.setdefault(DOMAIN, {})

    if not _discovery_disabled(hass):
        await _async_start_discovery(hass)

    return True


async def _async_start_discovery(hass: HomeAssistant) -> None:
    """Start discovery once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if DISCOVERY in domain_data:
        return

    _LOGGER.debug("Starting iTach discovery")

    discovery = ItachDiscovery(hass)
    await discovery.async_start()
    domain_data[DISCOVERY] = discovery

    async def _async_stop_discovery(event: Event) -> None:
        """Stop discovery when Home Assistant stops."""
        discovery: ItachDiscovery | None = hass.data.get(DOMAIN, {}).pop(
            DISCOVERY,
            None,
        )
        if discovery:
            await discovery.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_discovery)


async def async_reload_entry(hass: HomeAssistant, entry: ItachConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ItachConfigEntry) -> bool:
    """Initialize the iTach integration from a config entry."""
    if not _discovery_disabled(hass):
        await _async_start_discovery(hass)

    if entry.unique_id is None:
        async_create_repair_issue(
            hass,
            _issue_id(ISSUE_INVALID_CONFIG, entry),
            translation_key=ISSUE_INVALID_CONFIG,
            placeholders={
                "host": str(entry.data.get(CONF_HOST, "unknown")),
                "entry_title": entry.title,
                "error": "Config entry is missing a unique_id",
            },
        )
        raise ValueError("Config entry is missing a unique_id")

    host = str(entry.options.get(CONF_HOST, entry.data[CONF_HOST]))
    port = int(entry.options.get(CONF_PORT, entry.data[CONF_PORT]))

    client = ItachClient(host, port)

    try:
        ir_capability = await async_get_ir_capability(client)
        ir_module = ir_capability.module
        ir_ports = ir_capability.ports
        client.max_connector = ir_ports
        ir_enabled_ports = ir_capability.enabled_ports
        ir_connector_modes = ir_capability.connector_modes
    except ItachConnectionError as err:
        await client.close()
        async_create_repair_issue(
            hass,
            _issue_id(ISSUE_CANNOT_CONNECT, entry),
            translation_key=ISSUE_CANNOT_CONNECT,
            placeholders={"host": host, "entry_title": entry.title},
        )
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key=ISSUE_CANNOT_CONNECT,
        ) from err
    except ItachError as err:
        await client.close()
        async_create_repair_issue(
            hass,
            _issue_id(ISSUE_INVALID_CONFIG, entry),
            translation_key=ISSUE_INVALID_CONFIG,
            placeholders={
                "host": host,
                "entry_title": entry.title,
                "error": str(err),
            },
        )
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key=ISSUE_INVALID_CONFIG,
        ) from err

    if not ir_enabled_ports:
        await client.close()
        async_create_repair_issue(
            hass,
            _issue_id(ISSUE_NO_IR_PORTS, entry),
            translation_key=ISSUE_NO_IR_PORTS,
            placeholders={"host": host, "entry_title": entry.title},
        )
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key=ISSUE_NO_IR_PORTS,
        )

    async_delete_repair_issue(hass, _issue_id(ISSUE_CANNOT_CONNECT, entry))
    async_delete_repair_issue(hass, _issue_id(ISSUE_INVALID_CONFIG, entry))
    async_delete_repair_issue(hass, _issue_id(ISSUE_NO_IR_PORTS, entry))

    if all(mode == "UNKNOWN" for mode in ir_connector_modes.values()):
        _LOGGER.warning(
            "Could not determine iTach IR connector output modes for %s:%s; "
            "falling back to all %s connector(s)",
            host,
            port,
            ir_ports,
        )

    entry.runtime_data = ItachRuntimeData(
        host=host,
        port=port,
        device_id=entry.unique_id,
        ir_module=ir_module,
        ir_ports=ir_ports,
        ir_enabled_ports=ir_enabled_ports,
        ir_connector_modes=ir_connector_modes,
        client=client,
    )
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ItachConfigEntry) -> bool:
    """Unload an iTach config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.client.close()

    return unload_ok
