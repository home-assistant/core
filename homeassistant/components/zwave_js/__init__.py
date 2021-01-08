"""The Z-Wave JS integration."""
import asyncio
import logging

from async_timeout import timeout
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.node import Node as ZwaveNode

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN, PLATFORMS
from .discovery import async_discover_values

LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Z-Wave JS component."""
    hass.data[DOMAIN] = {}
    return True


@callback
def register_node_in_dev_reg(
    entry: ConfigEntry,
    dev_reg: device_registry.DeviceRegistry,
    client: ZwaveClient,
    node: ZwaveNode,
) -> None:
    """Register node in dev reg."""
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, client.driver.controller.home_id, node.node_id)},
        sw_version=node.firmware_version,
        name=node.name or node.device_config.description,
        model=node.device_config.label or str(node.product_type),
        manufacturer=node.device_config.manufacturer or str(node.manufacturer_id),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Z-Wave JS from a config entry."""
    client = ZwaveClient(entry.data[CONF_URL], async_get_clientsession(hass))
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_UNSUBSCRIBE: [],
    }
    initialized = asyncio.Event()
    discovered_values = set()

    # pylint: disable=fixme

    async def async_on_initialized():
        """Handle initial full state received."""
        # TODO: signal entities to update availability state
        LOGGER.info("Connection to Zwave JS Server initialized")
        initialized.set()

        # run discovery on all ready nodes
        for node in client.driver.controller.nodes.values():
            if not node.ready:
                continue
            asyncio.create_task(async_on_node_ready(node))
        # TODO: register callback for "node_ready" event

    async def async_on_disconnect():
        """Handle websocket is disconnected."""
        LOGGER.info("Disconnected from Zwave JS Server")
        # TODO: signal entities to update availability state

    async def async_on_node_ready(node: ZwaveNode):
        """Handle node ready event."""
        LOGGER.debug("Processing node %s", node)
        # register (or update) node in device registry
        dev_reg = await device_registry.async_get_registry(hass)
        register_node_in_dev_reg(entry, dev_reg, client, node)
        # run discovery on all node values and create/update entities
        async for disc_info in async_discover_values(node):
            LOGGER.debug("Discovered entity: %s", disc_info)
            if disc_info.discovery_id not in discovered_values:
                # dispatch discovery_info to platform
                discovered_values.add(disc_info.discovery_id)
                async_dispatcher_send(hass, f"{DOMAIN}_add_{disc_info.platform}", disc_info)
            else:
                # already discovered, dispatch update request
                async_dispatcher_send(
                    hass, f"{DOMAIN}_update_{disc_info.discovery_id}", disc_info.primary_value
                )

    # register main event callbacks.
    hass.data[DOMAIN][entry.entry_id][DATA_UNSUBSCRIBE] += [
        client.register_on_initialized(async_on_initialized),
        client.register_on_disconnect(async_on_disconnect),
    ]

    async def async_connect():
        """Start platforms and connect."""
        # start platforms
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, platform)
                for platform in PLATFORMS
            ]
        )
        # connect and throw error if connection failed
        await client.connect()
        try:
            async with timeout(10):
                await initialized.wait()
        except asyncio.TimeoutError as err:
            for unsub in hass.data[DOMAIN][entry.entry_id][DATA_UNSUBSCRIBE]:
                unsub()
            await client.disconnect()
            raise ConfigEntryNotReady from err

    asyncio.create_task(async_connect())

    async def handle_ha_shutdown(event):
        """Handle HA shutdown."""
        await client.disconnect()

    hass.data[DOMAIN][entry.entry_id][DATA_UNSUBSCRIBE].append(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, handle_ha_shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if not unload_ok:
        return False

    info = hass.data[DOMAIN].pop(entry.entry_id)

    for unsub in info[DATA_UNSUBSCRIBE]:
        unsub()

    await info[DATA_CLIENT].disconnect()

    return True
