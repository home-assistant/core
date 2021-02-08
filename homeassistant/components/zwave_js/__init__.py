"""The Z-Wave JS integration."""
import asyncio
import logging
from typing import Callable, List

from async_timeout import timeout
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.exceptions import BaseZwaveJSServerError
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.notification import Notification
from zwave_js_server.model.value import ValueNotification

from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import async_register_api
from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_COMMAND_CLASS_NAME,
    ATTR_DEVICE_ID,
    ATTR_DOMAIN,
    ATTR_ENDPOINT,
    ATTR_HOME_ID,
    ATTR_LABEL,
    ATTR_NODE_ID,
    ATTR_PARAMETERS,
    ATTR_PROPERTY_KEY_NAME,
    ATTR_PROPERTY_NAME,
    ATTR_TYPE,
    ATTR_VALUE,
    CONF_INTEGRATION_CREATED_ADDON,
    DATA_CLIENT,
    DATA_UNSUBSCRIBE,
    DOMAIN,
    EVENT_DEVICE_ADDED_TO_REGISTRY,
    PLATFORMS,
    ZWAVE_JS_EVENT,
)
from .discovery import async_discover_values
from .entity import get_device_id

LOGGER = logging.getLogger(__package__)
CONNECT_TIMEOUT = 10
DATA_CLIENT_LISTEN_TASK = "client_listen_task"
DATA_START_PLATFORM_TASK = "start_platform_task"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Z-Wave JS component."""
    hass.data[DOMAIN] = {}
    return True


@callback
def register_node_in_dev_reg(
    hass: HomeAssistant,
    entry: ConfigEntry,
    dev_reg: device_registry.DeviceRegistry,
    client: ZwaveClient,
    node: ZwaveNode,
) -> None:
    """Register node in dev reg."""
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={get_device_id(client, node)},
        sw_version=node.firmware_version,
        name=node.name or node.device_config.description or f"Node {node.node_id}",
        model=node.device_config.label,
        manufacturer=node.device_config.manufacturer,
    )

    async_dispatcher_send(hass, EVENT_DEVICE_ADDED_TO_REGISTRY, device)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Z-Wave JS from a config entry."""
    client = ZwaveClient(entry.data[CONF_URL], async_get_clientsession(hass))
    dev_reg = await device_registry.async_get_registry(hass)

    @callback
    def async_on_node_ready(node: ZwaveNode) -> None:
        """Handle node ready event."""
        LOGGER.debug("Processing node %s", node)

        # register (or update) node in device registry
        register_node_in_dev_reg(hass, entry, dev_reg, client, node)

        # run discovery on all node values and create/update entities
        for disc_info in async_discover_values(node):
            LOGGER.debug("Discovered entity: %s", disc_info)
            async_dispatcher_send(
                hass, f"{DOMAIN}_{entry.entry_id}_add_{disc_info.platform}", disc_info
            )
        # add listener for stateless node value notification events
        node.on(
            "value notification",
            lambda event: async_on_value_notification(event["value_notification"]),
        )
        # add listener for stateless node notification events
        node.on(
            "notification", lambda event: async_on_notification(event["notification"])
        )

    @callback
    def async_on_node_added(node: ZwaveNode) -> None:
        """Handle node added event."""
        # we only want to run discovery when the node has reached ready state,
        # otherwise we'll have all kinds of missing info issues.
        if node.ready:
            async_on_node_ready(node)
            return
        # if node is not yet ready, register one-time callback for ready state
        LOGGER.debug("Node added: %s - waiting for it to become ready.", node.node_id)
        node.once(
            "ready",
            lambda event: async_on_node_ready(event["node"]),
        )
        # we do submit the node to device registry so user has
        # some visual feedback that something is (in the process of) being added
        register_node_in_dev_reg(hass, entry, dev_reg, client, node)

    @callback
    def async_on_node_removed(node: ZwaveNode) -> None:
        """Handle node removed event."""
        # grab device in device registry attached to this node
        dev_id = get_device_id(client, node)
        device = dev_reg.async_get_device({dev_id})
        # note: removal of entity registry is handled by core
        dev_reg.async_remove_device(device.id)

    @callback
    def async_on_value_notification(notification: ValueNotification) -> None:
        """Relay stateless value notification events from Z-Wave nodes to hass."""
        device = dev_reg.async_get_device({get_device_id(client, notification.node)})
        value = notification.value
        if notification.metadata.states:
            value = notification.metadata.states.get(str(value), value)
        hass.bus.async_fire(
            ZWAVE_JS_EVENT,
            {
                ATTR_TYPE: "value_notification",
                ATTR_DOMAIN: DOMAIN,
                ATTR_NODE_ID: notification.node.node_id,
                ATTR_HOME_ID: client.driver.controller.home_id,
                ATTR_ENDPOINT: notification.endpoint,
                ATTR_DEVICE_ID: device.id,
                ATTR_COMMAND_CLASS: notification.command_class,
                ATTR_COMMAND_CLASS_NAME: notification.command_class_name,
                ATTR_LABEL: notification.metadata.label,
                ATTR_PROPERTY_NAME: notification.property_name,
                ATTR_PROPERTY_KEY_NAME: notification.property_key_name,
                ATTR_VALUE: value,
            },
        )

    @callback
    def async_on_notification(notification: Notification) -> None:
        """Relay stateless notification events from Z-Wave nodes to hass."""
        device = dev_reg.async_get_device({get_device_id(client, notification.node)})
        hass.bus.async_fire(
            ZWAVE_JS_EVENT,
            {
                ATTR_TYPE: "notification",
                ATTR_DOMAIN: DOMAIN,
                ATTR_NODE_ID: notification.node.node_id,
                ATTR_HOME_ID: client.driver.controller.home_id,
                ATTR_DEVICE_ID: device.id,
                ATTR_LABEL: notification.notification_label,
                ATTR_PARAMETERS: notification.parameters,
            },
        )

    # connect and throw error if connection failed
    try:
        async with timeout(CONNECT_TIMEOUT):
            await client.connect()
    except (asyncio.TimeoutError, BaseZwaveJSServerError) as err:
        raise ConfigEntryNotReady from err
    else:
        LOGGER.info("Connected to Zwave JS Server")

    unsubscribe_callbacks: List[Callable] = []
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_UNSUBSCRIBE: unsubscribe_callbacks,
    }

    # Set up websocket API
    async_register_api(hass)

    async def start_platforms() -> None:
        """Start platforms and perform discovery."""
        # wait until all required platforms are ready
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, component)
                for component in PLATFORMS
            ]
        )

        driver_ready = asyncio.Event()

        async def handle_ha_shutdown(event: Event) -> None:
            """Handle HA shutdown."""
            await disconnect_client(hass, entry, client, listen_task, platform_task)

        listen_task = asyncio.create_task(
            client_listen(hass, entry, client, driver_ready)
        )
        hass.data[DOMAIN][entry.entry_id][DATA_CLIENT_LISTEN_TASK] = listen_task
        unsubscribe_callbacks.append(
            hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, handle_ha_shutdown)
        )

        await driver_ready.wait()

        LOGGER.info("Connection to Zwave JS Server initialized")

        # Check for nodes that no longer exist and remove them
        stored_devices = device_registry.async_entries_for_config_entry(
            dev_reg, entry.entry_id
        )
        known_devices = [
            dev_reg.async_get_device({get_device_id(client, node)})
            for node in client.driver.controller.nodes.values()
        ]

        # Devices that are in the device registry that are not known by the controller can be removed
        for device in stored_devices:
            if device not in known_devices:
                dev_reg.async_remove_device(device.id)

        # run discovery on all ready nodes
        for node in client.driver.controller.nodes.values():
            async_on_node_added(node)

        # listen for new nodes being added to the mesh
        client.driver.controller.on(
            "node added", lambda event: async_on_node_added(event["node"])
        )
        # listen for nodes being removed from the mesh
        # NOTE: This will not remove nodes that were removed when HA was not running
        client.driver.controller.on(
            "node removed", lambda event: async_on_node_removed(event["node"])
        )

    platform_task = hass.async_create_task(start_platforms())
    hass.data[DOMAIN][entry.entry_id][DATA_START_PLATFORM_TASK] = platform_task

    return True


async def client_listen(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: ZwaveClient,
    driver_ready: asyncio.Event,
) -> None:
    """Listen with the client."""
    should_reload = True
    try:
        await client.listen(driver_ready)
    except asyncio.CancelledError:
        should_reload = False
    except BaseZwaveJSServerError:
        pass

    # The entry needs to be reloaded since a new driver state
    # will be acquired on reconnect.
    # All model instances will be replaced when the new state is acquired.
    if should_reload:
        LOGGER.info("Disconnected from server. Reloading integration")
        asyncio.create_task(hass.config_entries.async_reload(entry.entry_id))


async def disconnect_client(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: ZwaveClient,
    listen_task: asyncio.Task,
    platform_task: asyncio.Task,
) -> None:
    """Disconnect client."""
    listen_task.cancel()
    platform_task.cancel()

    await asyncio.gather(listen_task, platform_task)

    if client.connected:
        await client.disconnect()
        LOGGER.info("Disconnected from Zwave JS Server")


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

    if DATA_CLIENT_LISTEN_TASK in info:
        await disconnect_client(
            hass,
            entry,
            info[DATA_CLIENT],
            info[DATA_CLIENT_LISTEN_TASK],
            platform_task=info[DATA_START_PLATFORM_TASK],
        )

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    if not entry.data.get(CONF_INTEGRATION_CREATED_ADDON):
        return

    try:
        await hass.components.hassio.async_stop_addon("core_zwave_js")
    except HassioAPIError as err:
        LOGGER.error("Failed to stop the Z-Wave JS add-on: %s", err)
        return
    try:
        await hass.components.hassio.async_uninstall_addon("core_zwave_js")
    except HassioAPIError as err:
        LOGGER.error("Failed to uninstall the Z-Wave JS add-on: %s", err)
