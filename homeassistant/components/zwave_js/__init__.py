"""The Z-Wave JS integration."""
import asyncio
import logging

from async_timeout import timeout
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.node import Node as ZwaveNode

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN, PLATFORMS
from .discovery import async_discover_values

LOGGER = logging.getLogger(__name__)
CONNECT_TIMEOUT = 10


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
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
        identifiers={(DOMAIN, f"{client.driver.controller.home_id}-{node.node_id}")},
        sw_version=node.firmware_version,
        name=node.name or node.device_config.description,
        model=node.device_config.label or str(node.product_type),
        manufacturer=node.device_config.manufacturer or str(node.manufacturer_id),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Z-Wave JS from a config entry."""
    client = ZwaveClient(entry.data[CONF_URL], async_get_clientsession(hass))
    initialized = asyncio.Event()
    dev_reg = await device_registry.async_get_registry(hass)

    async def async_on_connect() -> None:
        """Handle websocket is (re)connected."""
        LOGGER.info("Connected to Zwave JS Server")
        if initialized.is_set():
            # update entity availability
            async_dispatcher_send(hass, f"{DOMAIN}_connection_state")

    async def async_on_disconnect() -> None:
        """Handle websocket is disconnected."""
        LOGGER.info("Disconnected from Zwave JS Server")
        async_dispatcher_send(hass, f"{DOMAIN}_connection_state")

    async def async_on_initialized() -> None:
        """Handle initial full state received."""
        LOGGER.info("Connection to Zwave JS Server initialized.")
        initialized.set()

    @callback
    def async_on_node_ready(node: ZwaveNode) -> None:
        """Handle node ready event."""
        LOGGER.debug("Processing node %s", node)

        # register (or update) node in device registry
        register_node_in_dev_reg(entry, dev_reg, client, node)

        # run discovery on all node values and create/update entities
        for disc_info in async_discover_values(node):
            LOGGER.debug("Discovered entity: %s", disc_info)
            async_dispatcher_send(hass, f"{DOMAIN}_add_{disc_info.platform}", disc_info)

    @callback
    def async_on_node_added(node: ZwaveNode) -> None:
        """Handle node added event."""
        LOGGER.debug("Node added: %s - waiting for it to become ready.", node.node_id)
        # we only want to run discovery when the node has reached ready state,
        # otherwise we'll have all kinds of missing info issues.
        if node.ready:
            async_on_node_ready(node)
            return
        # if node is not yet ready, register one-time callback for ready state
        node.once(
            "ready",
            lambda event: async_on_node_ready(event["node"]),
        )
        # we do submit the node to device registry so user has
        # some visual feedback that something is (in the process of) being added
        register_node_in_dev_reg(entry, dev_reg, client, node)

    async def handle_ha_shutdown(event: Event) -> None:
        """Handle HA shutdown."""
        await client.disconnect()

    # register main event callbacks.
    unsubs = [
        client.register_on_initialized(async_on_initialized),
        client.register_on_disconnect(async_on_disconnect),
        client.register_on_connect(async_on_connect),
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, handle_ha_shutdown),
    ]

    # connect and throw error if connection failed
    asyncio.create_task(client.connect())
    try:
        async with timeout(CONNECT_TIMEOUT):
            await initialized.wait()
    except asyncio.TimeoutError as err:
        for unsub in unsubs:
            unsub()
        await client.disconnect()
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_UNSUBSCRIBE: unsubs,
    }

    async def start_platforms() -> None:
        """Start platforms and perform discovery."""
        # wait until all required platforms are ready
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, component)
                for component in PLATFORMS
            ]
        )

        # run discovery on all ready nodes
        for node in client.driver.controller.nodes.values():
            if node.ready:
                async_on_node_ready(node)
                continue
            # if node is not yet ready, register one-time callback for ready state
            node.once(
                "ready",
                lambda event: async_on_node_ready(event["node"]),
            )
        # listen for new nodes being added to the mesh
        client.driver.controller.on(
            "node added", lambda event: async_on_node_added(event["node"])
        )

    hass.async_create_task(start_platforms())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
