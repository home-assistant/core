"""The PowerShades integration."""

import logging

from getmac import get_mac_address

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, OP_GET_SERIAL
from .coordinator import PowerShadesConfigEntry, PowerShadesCoordinator
from .discovery import async_start_discovery
from .protocol import parse_serial_reply
from .services import async_setup_services
from .udp import PowerShadesConnection, PowerShadesTimeoutError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.COVER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def _async_update_device_metadata(
    hass: HomeAssistant,
    entry: PowerShadesConfigEntry,
    coordinator: PowerShadesCoordinator,
) -> None:
    """Fill in MAC and model metadata missing from the entry.

    Called right after a successful first refresh, so the device is
    known reachable and the ARP cache is warm from the UDP exchange.
    Best-effort: silently keeps the entry unchanged on lookup failure.
    """
    updates: dict[str, str | int] = {}

    mac = await hass.async_add_executor_job(
        lambda: get_mac_address(ip=entry.data["ip"])
    )
    if mac and mac != "00:00:00:00:00:00":
        mac = format_mac(mac)
        coordinator.mac_address = mac
        if mac != entry.data.get("mac"):
            updates["mac"] = mac

    if entry.data.get("model") is None:
        try:
            reply = await coordinator.connection.async_request(OP_GET_SERIAL)
        except PowerShadesTimeoutError:
            reply = None
        parsed = parse_serial_reply(reply) if reply else None
        if parsed is not None:
            coordinator.model = parsed["model"]
            updates["model"] = parsed["model"]

    if updates:
        _LOGGER.debug("Updating metadata for shade %s: %s", entry.data["ip"], updates)
        hass.config_entries.async_update_entry(entry, data={**entry.data, **updates})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the PowerShades component."""
    async_setup_services(hass)
    async_start_discovery(hass)
    return True


def _cannot_connect_issue_id(entry: PowerShadesConfigEntry) -> str:
    """Return the repair issue ID for a setup-failure of this entry."""
    return f"cannot_connect_{entry.entry_id}"


async def async_setup_entry(hass: HomeAssistant, entry: PowerShadesConfigEntry) -> bool:
    """Set up PowerShades from a config entry."""
    connection = PowerShadesConnection(entry.data["ip"])
    await connection.async_connect()

    coordinator = PowerShadesCoordinator(hass, entry, connection)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        connection.close()
        ir.async_create_issue(
            hass,
            DOMAIN,
            _cannot_connect_issue_id(entry),
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="cannot_connect",
            translation_placeholders={"name": entry.title, "ip": entry.data["ip"]},
        )
        raise

    ir.async_delete_issue(hass, DOMAIN, _cannot_connect_issue_id(entry))

    entry.runtime_data = coordinator
    entry.async_on_unload(connection.close)

    await _async_update_device_metadata(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PowerShadesConfigEntry
) -> bool:
    """Unload a config entry."""
    ir.async_delete_issue(hass, DOMAIN, _cannot_connect_issue_id(entry))
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
