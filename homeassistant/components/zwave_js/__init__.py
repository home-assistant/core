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
from homeassistant.const import ATTR_DOMAIN, CONF_URL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import async_register_api
from .const import (
    ADDON_SLUG,
    ATTR_COMMAND_CLASS,
    ATTR_COMMAND_CLASS_NAME,
    ATTR_DEVICE_ID,
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
from .helpers import get_device_id, get_old_value_id, get_unique_id
from .services import ZWaveServices

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
    ent_reg = entity_registry.async_get(hass)

    @callback
    def migrate_entity(platform: str, old_unique_id: str, new_unique_id: str) -> None:
        """Check if entity with old unique ID exists, and if so migrate it to new ID."""
        if entity_id := ent_reg.async_get_entity_id(platform, DOMAIN, old_unique_id):
            LOGGER.debug(
                "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
                entity_id,
                old_unique_id,
                new_unique_id,
            )
            try:
                ent_reg.async_update_entity(
                    entity_id,
                    new_unique_id=new_unique_id,
                )
            except ValueError:
                LOGGER.debug(
                    (
                        "Entity %s can't be migrated because the unique ID is taken. "
                        "Cleaning it up since it is likely no longer valid."
                    ),
                    entity_id,
                )
                ent_reg.async_remove(entity_id)

    @callback
    def async_on_node_ready(node: ZwaveNode) -> None:
        """Handle node ready event."""
        LOGGER.debug("Processing node %s", node)

        # register (or update) node in device registry
        register_node_in_dev_reg(hass, entry, dev_reg, client, node)

        # run discovery on all node values and create/update entities
        for disc_info in async_discover_values(node):
            LOGGER.debug("Discovered entity: %s", disc_info)

            # This migration logic was added in 2021.3 to handle a breaking change to
            # the value_id format. Some time in the future, this code block
            # (as well as get_old_value_id helper and migrate_entity closure) can be
            # removed.
            value_ids = [
                # 2021.2.* format
                get_old_value_id(disc_info.primary_value),
                # 2021.3.0b0 format
                disc_info.primary_value.value_id,
            ]

            new_unique_id = get_unique_id(
                client.driver.controller.home_id,
                disc_info.primary_value.value_id,
            )

            for value_id in value_ids:
                old_unique_id = get_unique_id(
                    client.driver.controller.home_id,
                    f"{disc_info.primary_value.node.node_id}.{value_id}",
                )
                # Most entities have the same ID format, but notification binary sensors
                # have a state key in their ID so we need to handle them differently
                if (
                    disc_info.platform == "binary_sensor"
                    and disc_info.platform_hint == "notification"
                ):
                    for state_key in disc_info.primary_value.metadata.states:
                        # ignore idle key (0)
                        if state_key == "0":
                            continue

                        migrate_entity(
                            disc_info.platform,
                            f"{old_unique_id}.{state_key}",
                            f"{new_unique_id}.{state_key}",
                        )

                    # Once we've iterated through all state keys, we can move on to the
                    # next item
                    continue

                migrate_entity(disc_info.platform, old_unique_id, new_unique_id)

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
        # note: removal of entity registry entry is handled by core
        dev_reg.async_remove_device(device.id)  # type: ignore

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
                ATTR_DEVICE_ID: device.id,  # type: ignore
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
                ATTR_DEVICE_ID: device.id,  # type: ignore
                ATTR_LABEL: notification.notification_label,
                ATTR_PARAMETERS: notification.parameters,
            },
        )

    # connect and throw error if connection failed
    try:
        async with timeout(CONNECT_TIMEOUT):
            await client.connect()
    except (asyncio.TimeoutError, BaseZwaveJSServerError) as err:
        LOGGER.error("Failed to connect: %s", err)
        raise ConfigEntryNotReady from err
    else:
        LOGGER.info("Connected to Zwave JS Server")

    unsubscribe_callbacks: List[Callable] = []
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_UNSUBSCRIBE: unsubscribe_callbacks,
    }

    services = ZWaveServices(hass, ent_reg)
    services.async_register()

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

        try:
            await driver_ready.wait()
        except asyncio.CancelledError:
            LOGGER.debug("Cancelling start platforms")
            return

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
    except BaseZwaveJSServerError as err:
        LOGGER.error("Failed to listen: %s", err)
    except Exception as err:  # pylint: disable=broad-except
        # We need to guard against unknown exceptions to not crash this task.
        LOGGER.exception("Unexpected exception: %s", err)

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
        await hass.components.hassio.async_stop_addon(ADDON_SLUG)
    except HassioAPIError as err:
        LOGGER.error("Failed to stop the Z-Wave JS add-on: %s", err)
        return
    try:
        await hass.components.hassio.async_uninstall_addon(ADDON_SLUG)
    except HassioAPIError as err:
        LOGGER.error("Failed to uninstall the Z-Wave JS add-on: %s", err)
