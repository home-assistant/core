"""The Homee integration."""

import logging

from pyHomee import Homee, HomeeAuthFailedException, HomeeConnectionFailedException
from pyHomee.model import HomeeNode

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.EVENT,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VALVE,
]

type HomeeConfigEntry = ConfigEntry[Homee]


async def async_setup_entry(hass: HomeAssistant, entry: HomeeConfigEntry) -> bool:
    """Set up homee from a config entry."""
    # Create the Homee api object using host, user,
    # password & pyHomee instance from the config
    homee = Homee(
        host=entry.data[CONF_HOST],
        user=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        device="HA_" + hass.config.location_name,
        reconnect_interval=10,
        max_retries=100,
    )

    # Start the homee websocket connection as a new task
    # and wait until we are connected
    try:
        await homee.get_access_token()
    except HomeeConnectionFailedException as exc:
        raise ConfigEntryNotReady(f"Connection to Homee failed: {exc.reason}") from exc
    except HomeeAuthFailedException as exc:
        raise ConfigEntryAuthFailed(
            f"Authentication to Homee failed: {exc.reason}"
        ) from exc

    hass.loop.create_task(homee.run())
    await homee.wait_until_connected()

    entry.runtime_data = homee
    entry.async_on_unload(homee.disconnect)

    async def _connection_update_callback(connected: bool) -> None:
        """Call when the device is notified of changes."""
        if connected:
            _LOGGER.warning("Reconnected to Homee at %s", entry.data[CONF_HOST])
        else:
            _LOGGER.warning("Disconnected from Homee at %s", entry.data[CONF_HOST])

    homee.add_connection_listener(_connection_update_callback)

    # create device register entry
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={
            (dr.CONNECTION_NETWORK_MAC, dr.format_mac(homee.settings.mac_address))
        },
        identifiers={(DOMAIN, homee.settings.uid)},
        manufacturer="homee",
        name=homee.settings.homee_name,
        model="homee",
        sw_version=homee.settings.version,
    )

    # Remove devices that are no longer present in homee.
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    for device in devices:
        # Check if the device is still present in homee
        device_identifiers = {identifier[1] for identifier in device.identifiers}
        # homee itself uses just the uid, nodes use {uid}-{nodeid}
        if homee.settings.uid in device_identifiers:
            continue  # Hub itself is never removed.
        is_node_present = any(
            f"{homee.settings.uid}-{node.id}" in device_identifiers
            for node in homee.nodes
        )
        if not is_node_present:
            _LOGGER.info("Removing device %s", device.name)
            device_registry.async_update_device(
                device_id=device.id,
                remove_config_entry_id=entry.entry_id,
            )

    # Remove device at runtime when node is removed in homee
    async def _remove_node_callback(node: HomeeNode, add: bool) -> None:
        """Call when a node is removed."""
        if add:
            return
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"{entry.runtime_data.settings.uid}-{node.id}")}
        )
        if device:
            _LOGGER.info("Removing device %s", device.name)
            device_registry.async_update_device(
                device_id=device.id,
                remove_config_entry_id=entry.entry_id,
            )

    homee.add_nodes_listener(_remove_node_callback)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomeeConfigEntry) -> bool:
    """Unload a homee config entry."""
    # Unload platforms
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
