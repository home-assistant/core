"""The Z-Wave JS integration."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Coroutine
from typing import Any

from async_timeout import timeout
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass
from zwave_js_server.exceptions import BaseZwaveJSServerError, InvalidServerVersion
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.notification import (
    EntryControlNotification,
    MultilevelSwitchNotification,
    NotificationNotification,
    PowerLevelNotification,
)
from zwave_js_server.model.value import Value, ValueNotification

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    CONF_URL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import UNDEFINED, ConfigType

from .addon import AddonError, AddonManager, AddonState, get_addon_manager
from .api import async_register_api
from .const import (
    ATTR_ACKNOWLEDGED_FRAMES,
    ATTR_COMMAND_CLASS,
    ATTR_COMMAND_CLASS_NAME,
    ATTR_DATA_TYPE,
    ATTR_DATA_TYPE_LABEL,
    ATTR_DIRECTION,
    ATTR_ENDPOINT,
    ATTR_EVENT,
    ATTR_EVENT_DATA,
    ATTR_EVENT_LABEL,
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPE_LABEL,
    ATTR_HOME_ID,
    ATTR_LABEL,
    ATTR_NODE_ID,
    ATTR_PARAMETERS,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    ATTR_PROPERTY_KEY_NAME,
    ATTR_PROPERTY_NAME,
    ATTR_STATUS,
    ATTR_TEST_NODE_ID,
    ATTR_TYPE,
    ATTR_VALUE,
    ATTR_VALUE_RAW,
    CONF_ADDON_DEVICE,
    CONF_ADDON_NETWORK_KEY,
    CONF_ADDON_S0_LEGACY_KEY,
    CONF_ADDON_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_S2_AUTHENTICATED_KEY,
    CONF_ADDON_S2_UNAUTHENTICATED_KEY,
    CONF_DATA_COLLECTION_OPTED_IN,
    CONF_INTEGRATION_CREATED_ADDON,
    CONF_NETWORK_KEY,
    CONF_S0_LEGACY_KEY,
    CONF_S2_ACCESS_CONTROL_KEY,
    CONF_S2_AUTHENTICATED_KEY,
    CONF_S2_UNAUTHENTICATED_KEY,
    CONF_USB_PATH,
    CONF_USE_ADDON,
    DATA_CLIENT,
    DOMAIN,
    EVENT_DEVICE_ADDED_TO_REGISTRY,
    LOGGER,
    ZWAVE_JS_NOTIFICATION_EVENT,
    ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
    ZWAVE_JS_VALUE_UPDATED_EVENT,
)
from .discovery import (
    ZwaveDiscoveryInfo,
    async_discover_node_values,
    async_discover_single_value,
)
from .helpers import (
    async_enable_statistics,
    get_device_id,
    get_device_id_ext,
    get_unique_id,
    get_valueless_base_unique_id,
)
from .migrate import async_migrate_discovered_value
from .services import ZWaveServices

CONNECT_TIMEOUT = 10
DATA_CLIENT_LISTEN_TASK = "client_listen_task"
DATA_DRIVER_EVENTS = "driver_events"
DATA_START_CLIENT_TASK = "start_client_task"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Z-Wave JS component."""
    hass.data[DOMAIN] = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        if not isinstance(entry.unique_id, str):
            hass.config_entries.async_update_entry(
                entry, unique_id=str(entry.unique_id)
            )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Z-Wave JS from a config entry."""
    if use_addon := entry.data.get(CONF_USE_ADDON):
        await async_ensure_addon_running(hass, entry)

    client = ZwaveClient(entry.data[CONF_URL], async_get_clientsession(hass))

    # connect and throw error if connection failed
    try:
        async with timeout(CONNECT_TIMEOUT):
            await client.connect()
    except InvalidServerVersion as err:
        if use_addon:
            async_ensure_addon_updated(hass)
        raise ConfigEntryNotReady(f"Invalid server version: {err}") from err
    except (asyncio.TimeoutError, BaseZwaveJSServerError) as err:
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err
    else:
        LOGGER.info("Connected to Zwave JS Server")

    dev_reg = device_registry.async_get(hass)
    ent_reg = entity_registry.async_get(hass)
    services = ZWaveServices(hass, ent_reg, dev_reg)
    services.async_register()

    # Set up websocket API
    async_register_api(hass)

    # Create a task to allow the config entry to be unloaded before the driver is ready.
    # Unloading the config entry is needed if the client listen task errors.
    start_client_task = hass.async_create_task(start_client(hass, entry, client))
    hass.data[DOMAIN].setdefault(entry.entry_id, {})[
        DATA_START_CLIENT_TASK
    ] = start_client_task

    return True


async def start_client(
    hass: HomeAssistant, entry: ConfigEntry, client: ZwaveClient
) -> None:
    """Start listening with the client."""
    entry_hass_data: dict = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    entry_hass_data[DATA_CLIENT] = client
    driver_events = entry_hass_data[DATA_DRIVER_EVENTS] = DriverEvents(hass, entry)

    async def handle_ha_shutdown(event: Event) -> None:
        """Handle HA shutdown."""
        await disconnect_client(hass, entry)

    listen_task = asyncio.create_task(
        client_listen(hass, entry, client, driver_events.ready)
    )
    entry_hass_data[DATA_CLIENT_LISTEN_TASK] = listen_task
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, handle_ha_shutdown)
    )

    try:
        await driver_events.ready.wait()
    except asyncio.CancelledError:
        LOGGER.debug("Cancelling start client")
        return

    LOGGER.info("Connection to Zwave JS Server initialized")

    if client.driver is None:
        raise RuntimeError("Driver not ready.")

    await driver_events.setup(client.driver)


class DriverEvents:
    """Represent driver events."""

    driver: Driver

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Set up the driver events instance."""
        self.config_entry = entry
        self.dev_reg = device_registry.async_get(hass)
        self.hass = hass
        self.platform_setup_tasks: dict[str, asyncio.Task] = {}
        self.ready = asyncio.Event()
        # Make sure to not pass self to ControllerEvents until all attributes are set.
        self.controller_events = ControllerEvents(hass, self)

    async def setup(self, driver: Driver) -> None:
        """Set up devices using the ready driver."""
        self.driver = driver

        # If opt in preference hasn't been specified yet, we do nothing, otherwise
        # we apply the preference
        if opted_in := self.config_entry.data.get(CONF_DATA_COLLECTION_OPTED_IN):
            await async_enable_statistics(driver)
        elif opted_in is False:
            await driver.async_disable_statistics()

        # Check for nodes that no longer exist and remove them
        stored_devices = device_registry.async_entries_for_config_entry(
            self.dev_reg, self.config_entry.entry_id
        )
        known_devices = [
            self.dev_reg.async_get_device({get_device_id(driver, node)})
            for node in driver.controller.nodes.values()
        ]

        # Devices that are in the device registry that are not known by the controller can be removed
        for device in stored_devices:
            if device not in known_devices:
                self.dev_reg.async_remove_device(device.id)

        # run discovery on all ready nodes
        await asyncio.gather(
            *(
                self.controller_events.async_on_node_added(node)
                for node in driver.controller.nodes.values()
            )
        )

        # listen for new nodes being added to the mesh
        self.config_entry.async_on_unload(
            driver.controller.on(
                "node added",
                lambda event: self.hass.async_create_task(
                    self.controller_events.async_on_node_added(event["node"])
                ),
            )
        )
        # listen for nodes being removed from the mesh
        # NOTE: This will not remove nodes that were removed when HA was not running
        self.config_entry.async_on_unload(
            driver.controller.on(
                "node removed", self.controller_events.async_on_node_removed
            )
        )

    async def async_setup_platform(self, platform: Platform) -> None:
        """Set up platform if needed."""
        if platform not in self.platform_setup_tasks:
            self.platform_setup_tasks[platform] = self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, platform
                )
            )
        await self.platform_setup_tasks[platform]


class ControllerEvents:
    """Represent controller events.

    Handle the following events:
    - node added
    - node removed
    """

    def __init__(self, hass: HomeAssistant, driver_events: DriverEvents) -> None:
        """Set up the controller events instance."""
        self.hass = hass
        self.config_entry = driver_events.config_entry
        self.discovered_value_ids: dict[str, set[str]] = defaultdict(set)
        self.driver_events = driver_events
        self.dev_reg = driver_events.dev_reg
        self.registered_unique_ids: dict[str, dict[str, set[str]]] = defaultdict(dict)
        self.node_events = NodeEvents(hass, self)

    @callback
    def remove_device(self, device: device_registry.DeviceEntry) -> None:
        """Remove device from registry."""
        # note: removal of entity registry entry is handled by core
        self.dev_reg.async_remove_device(device.id)
        self.registered_unique_ids.pop(device.id, None)
        self.discovered_value_ids.pop(device.id, None)

    async def async_on_node_added(self, node: ZwaveNode) -> None:
        """Handle node added event."""
        # No need for a ping button or node status sensor for controller nodes
        if not node.is_controller_node:
            # Create a node status sensor for each device
            await self.driver_events.async_setup_platform(Platform.SENSOR)
            async_dispatcher_send(
                self.hass,
                f"{DOMAIN}_{self.config_entry.entry_id}_add_node_status_sensor",
                node,
            )

            # Create a ping button for each device
            await self.driver_events.async_setup_platform(Platform.BUTTON)
            async_dispatcher_send(
                self.hass,
                f"{DOMAIN}_{self.config_entry.entry_id}_add_ping_button_entity",
                node,
            )

        LOGGER.debug("Node added: %s", node.node_id)

        # Listen for ready node events, both new and re-interview.
        self.config_entry.async_on_unload(
            node.on(
                "ready",
                lambda event: self.hass.async_create_task(
                    self.node_events.async_on_node_ready(event["node"])
                ),
            )
        )

        # we only want to run discovery when the node has reached ready state,
        # otherwise we'll have all kinds of missing info issues.
        if node.ready:
            await self.node_events.async_on_node_ready(node)
            return

        # we do submit the node to device registry so user has
        # some visual feedback that something is (in the process of) being added
        self.register_node_in_dev_reg(node)

    @callback
    def async_on_node_removed(self, event: dict) -> None:
        """Handle node removed event."""
        node: ZwaveNode = event["node"]
        replaced: bool = event.get("replaced", False)
        # grab device in device registry attached to this node
        dev_id = get_device_id(self.driver_events.driver, node)
        device = self.dev_reg.async_get_device({dev_id})
        # We assert because we know the device exists
        assert device
        if replaced:
            self.discovered_value_ids.pop(device.id, None)

            async_dispatcher_send(
                self.hass,
                f"{DOMAIN}_{get_valueless_base_unique_id(self.driver_events.driver, node)}_remove_entity",
            )
        else:
            self.remove_device(device)

    @callback
    def register_node_in_dev_reg(self, node: ZwaveNode) -> device_registry.DeviceEntry:
        """Register node in dev reg."""
        driver = self.driver_events.driver
        device_id = get_device_id(driver, node)
        device_id_ext = get_device_id_ext(driver, node)
        device = self.dev_reg.async_get_device({device_id})

        # Replace the device if it can be determined that this node is not the
        # same product as it was previously.
        if (
            device_id_ext
            and device
            and len(device.identifiers) == 2
            and device_id_ext not in device.identifiers
        ):
            self.remove_device(device)
            device = None

        if device_id_ext:
            ids = {device_id, device_id_ext}
        else:
            ids = {device_id}

        device = self.dev_reg.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers=ids,
            sw_version=node.firmware_version,
            name=node.name or node.device_config.description or f"Node {node.node_id}",
            model=node.device_config.label,
            manufacturer=node.device_config.manufacturer,
            suggested_area=node.location if node.location else UNDEFINED,
        )

        async_dispatcher_send(self.hass, EVENT_DEVICE_ADDED_TO_REGISTRY, device)

        return device


class NodeEvents:
    """Represent node events.

    Handle the following events:
    - ready
    - value added
    - value updated
    - metadata updated
    - value notification
    - notification
    """

    def __init__(
        self, hass: HomeAssistant, controller_events: ControllerEvents
    ) -> None:
        """Set up the node events instance."""
        self.config_entry = controller_events.config_entry
        self.controller_events = controller_events
        self.dev_reg = controller_events.dev_reg
        self.ent_reg = entity_registry.async_get(hass)
        self.hass = hass

    async def async_on_node_ready(self, node: ZwaveNode) -> None:
        """Handle node ready event."""
        LOGGER.debug("Processing node %s", node)
        driver = self.controller_events.driver_events.driver
        # register (or update) node in device registry
        device = self.controller_events.register_node_in_dev_reg(node)
        # We only want to create the defaultdict once, even on reinterviews
        if device.id not in self.controller_events.registered_unique_ids:
            self.controller_events.registered_unique_ids[device.id] = defaultdict(set)

        # Remove any old value ids if this is a reinterview.
        self.controller_events.discovered_value_ids.pop(device.id, None)
        # Remove stale entities that may exist from a previous interview.
        async_dispatcher_send(
            self.hass,
            (
                f"{DOMAIN}_"
                f"{get_valueless_base_unique_id(driver, node)}_"
                "remove_entity_on_ready_node"
            ),
        )

        value_updates_disc_info: dict[str, ZwaveDiscoveryInfo] = {}

        # run discovery on all node values and create/update entities
        await asyncio.gather(
            *(
                self.async_handle_discovery_info(
                    device, disc_info, value_updates_disc_info
                )
                for disc_info in async_discover_node_values(
                    node, device, self.controller_events.discovered_value_ids
                )
            )
        )

        # add listeners to handle new values that get added later
        for event in ("value added", "value updated", "metadata updated"):
            self.config_entry.async_on_unload(
                node.on(
                    event,
                    lambda event: self.hass.async_create_task(
                        self.async_on_value_added(
                            value_updates_disc_info, event["value"]
                        )
                    ),
                )
            )

        # add listener for stateless node value notification events
        self.config_entry.async_on_unload(
            node.on(
                "value notification",
                lambda event: self.async_on_value_notification(
                    event["value_notification"]
                ),
            )
        )

        # add listener for stateless node notification events
        self.config_entry.async_on_unload(
            node.on("notification", self.async_on_notification)
        )

        # Create a firmware update entity for each non-controller device that
        # supports firmware updates
        if not node.is_controller_node and any(
            CommandClass.FIRMWARE_UPDATE_MD.value == cc.id
            for cc in node.command_classes
        ):
            await self.controller_events.driver_events.async_setup_platform(
                Platform.UPDATE
            )
            async_dispatcher_send(
                self.hass,
                f"{DOMAIN}_{self.config_entry.entry_id}_add_firmware_update_entity",
                node,
            )

    async def async_handle_discovery_info(
        self,
        device: device_registry.DeviceEntry,
        disc_info: ZwaveDiscoveryInfo,
        value_updates_disc_info: dict[str, ZwaveDiscoveryInfo],
    ) -> None:
        """Handle discovery info and all dependent tasks."""
        # This migration logic was added in 2021.3 to handle a breaking change to
        # the value_id format. Some time in the future, this call (as well as the
        # helper functions) can be removed.
        async_migrate_discovered_value(
            self.hass,
            self.ent_reg,
            self.controller_events.registered_unique_ids[device.id][disc_info.platform],
            device,
            self.controller_events.driver_events.driver,
            disc_info,
        )

        platform = disc_info.platform
        await self.controller_events.driver_events.async_setup_platform(platform)

        LOGGER.debug("Discovered entity: %s", disc_info)
        async_dispatcher_send(
            self.hass,
            f"{DOMAIN}_{self.config_entry.entry_id}_add_{platform}",
            disc_info,
        )

        # If we don't need to watch for updates return early
        if not disc_info.assumed_state:
            return
        value_updates_disc_info[disc_info.primary_value.value_id] = disc_info
        # If this is not the first time we found a value we want to watch for updates,
        # return early because we only need one listener for all values.
        if len(value_updates_disc_info) != 1:
            return
        # add listener for value updated events
        self.config_entry.async_on_unload(
            disc_info.node.on(
                "value updated",
                lambda event: self.async_on_value_updated_fire_event(
                    value_updates_disc_info, event["value"]
                ),
            )
        )

    async def async_on_value_added(
        self, value_updates_disc_info: dict[str, ZwaveDiscoveryInfo], value: Value
    ) -> None:
        """Fire value updated event."""
        # If node isn't ready or a device for this node doesn't already exist, we can
        # let the node ready event handler perform discovery. If a value has already
        # been processed, we don't need to do it again
        device_id = get_device_id(
            self.controller_events.driver_events.driver, value.node
        )
        if (
            not value.node.ready
            or not (device := self.dev_reg.async_get_device({device_id}))
            or value.value_id in self.controller_events.discovered_value_ids[device.id]
        ):
            return

        LOGGER.debug("Processing node %s added value %s", value.node, value)
        await asyncio.gather(
            *(
                self.async_handle_discovery_info(
                    device, disc_info, value_updates_disc_info
                )
                for disc_info in async_discover_single_value(
                    value, device, self.controller_events.discovered_value_ids
                )
            )
        )

    @callback
    def async_on_value_notification(self, notification: ValueNotification) -> None:
        """Relay stateless value notification events from Z-Wave nodes to hass."""
        driver = self.controller_events.driver_events.driver
        device = self.dev_reg.async_get_device(
            {get_device_id(driver, notification.node)}
        )
        # We assert because we know the device exists
        assert device
        raw_value = value = notification.value
        if notification.metadata.states:
            value = notification.metadata.states.get(str(value), value)
        self.hass.bus.async_fire(
            ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
            {
                ATTR_DOMAIN: DOMAIN,
                ATTR_NODE_ID: notification.node.node_id,
                ATTR_HOME_ID: driver.controller.home_id,
                ATTR_ENDPOINT: notification.endpoint,
                ATTR_DEVICE_ID: device.id,
                ATTR_COMMAND_CLASS: notification.command_class,
                ATTR_COMMAND_CLASS_NAME: notification.command_class_name,
                ATTR_LABEL: notification.metadata.label,
                ATTR_PROPERTY: notification.property_,
                ATTR_PROPERTY_NAME: notification.property_name,
                ATTR_PROPERTY_KEY: notification.property_key,
                ATTR_PROPERTY_KEY_NAME: notification.property_key_name,
                ATTR_VALUE: value,
                ATTR_VALUE_RAW: raw_value,
            },
        )

    @callback
    def async_on_notification(self, event: dict[str, Any]) -> None:
        """Relay stateless notification events from Z-Wave nodes to hass."""
        if "notification" not in event:
            LOGGER.info("Unknown notification: %s", event)
            return

        driver = self.controller_events.driver_events.driver
        notification: EntryControlNotification | NotificationNotification | PowerLevelNotification | MultilevelSwitchNotification = event[
            "notification"
        ]
        device = self.dev_reg.async_get_device(
            {get_device_id(driver, notification.node)}
        )
        # We assert because we know the device exists
        assert device
        event_data = {
            ATTR_DOMAIN: DOMAIN,
            ATTR_NODE_ID: notification.node.node_id,
            ATTR_HOME_ID: driver.controller.home_id,
            ATTR_DEVICE_ID: device.id,
            ATTR_COMMAND_CLASS: notification.command_class,
        }

        if isinstance(notification, EntryControlNotification):
            event_data.update(
                {
                    ATTR_COMMAND_CLASS_NAME: "Entry Control",
                    ATTR_EVENT_TYPE: notification.event_type,
                    ATTR_EVENT_TYPE_LABEL: notification.event_type_label,
                    ATTR_DATA_TYPE: notification.data_type,
                    ATTR_DATA_TYPE_LABEL: notification.data_type_label,
                    ATTR_EVENT_DATA: notification.event_data,
                }
            )
        elif isinstance(notification, NotificationNotification):
            event_data.update(
                {
                    ATTR_COMMAND_CLASS_NAME: "Notification",
                    ATTR_LABEL: notification.label,
                    ATTR_TYPE: notification.type_,
                    ATTR_EVENT: notification.event,
                    ATTR_EVENT_LABEL: notification.event_label,
                    ATTR_PARAMETERS: notification.parameters,
                }
            )
        elif isinstance(notification, PowerLevelNotification):
            event_data.update(
                {
                    ATTR_COMMAND_CLASS_NAME: "Powerlevel",
                    ATTR_TEST_NODE_ID: notification.test_node_id,
                    ATTR_STATUS: notification.status,
                    ATTR_ACKNOWLEDGED_FRAMES: notification.acknowledged_frames,
                }
            )
        elif isinstance(notification, MultilevelSwitchNotification):
            event_data.update(
                {
                    ATTR_COMMAND_CLASS_NAME: "Multilevel Switch",
                    ATTR_EVENT_TYPE: notification.event_type,
                    ATTR_EVENT_TYPE_LABEL: notification.event_type_label,
                    ATTR_DIRECTION: notification.direction,
                }
            )
        else:
            raise TypeError(f"Unhandled notification type: {notification}")

        self.hass.bus.async_fire(ZWAVE_JS_NOTIFICATION_EVENT, event_data)

    @callback
    def async_on_value_updated_fire_event(
        self, value_updates_disc_info: dict[str, ZwaveDiscoveryInfo], value: Value
    ) -> None:
        """Fire value updated event."""
        # Get the discovery info for the value that was updated. If there is
        # no discovery info for this value, we don't need to fire an event
        if value.value_id not in value_updates_disc_info:
            return

        driver = self.controller_events.driver_events.driver
        disc_info = value_updates_disc_info[value.value_id]

        device = self.dev_reg.async_get_device({get_device_id(driver, value.node)})
        # We assert because we know the device exists
        assert device

        unique_id = get_unique_id(driver, disc_info.primary_value.value_id)
        entity_id = self.ent_reg.async_get_entity_id(
            disc_info.platform, DOMAIN, unique_id
        )

        raw_value = value_ = value.value
        if value.metadata.states:
            value_ = value.metadata.states.get(str(value), value_)

        self.hass.bus.async_fire(
            ZWAVE_JS_VALUE_UPDATED_EVENT,
            {
                ATTR_NODE_ID: value.node.node_id,
                ATTR_HOME_ID: driver.controller.home_id,
                ATTR_DEVICE_ID: device.id,
                ATTR_ENTITY_ID: entity_id,
                ATTR_COMMAND_CLASS: value.command_class,
                ATTR_COMMAND_CLASS_NAME: value.command_class_name,
                ATTR_ENDPOINT: value.endpoint,
                ATTR_PROPERTY: value.property_,
                ATTR_PROPERTY_NAME: value.property_name,
                ATTR_PROPERTY_KEY: value.property_key,
                ATTR_PROPERTY_KEY_NAME: value.property_key_name,
                ATTR_VALUE: value_,
                ATTR_VALUE_RAW: raw_value,
            },
        )


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
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def disconnect_client(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Disconnect client."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: ZwaveClient = data[DATA_CLIENT]
    listen_task: asyncio.Task = data[DATA_CLIENT_LISTEN_TASK]
    start_client_task: asyncio.Task = data[DATA_START_CLIENT_TASK]
    driver_events: DriverEvents = data[DATA_DRIVER_EVENTS]
    listen_task.cancel()
    start_client_task.cancel()
    platform_setup_tasks = driver_events.platform_setup_tasks.values()
    for task in platform_setup_tasks:
        task.cancel()

    await asyncio.gather(listen_task, start_client_task, *platform_setup_tasks)

    if client.connected:
        await client.disconnect()
        LOGGER.info("Disconnected from Zwave JS Server")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    info = hass.data[DOMAIN][entry.entry_id]
    driver_events: DriverEvents = info[DATA_DRIVER_EVENTS]

    tasks: list[asyncio.Task | Coroutine] = []
    for platform, task in driver_events.platform_setup_tasks.items():
        if task.done():
            tasks.append(
                hass.config_entries.async_forward_entry_unload(entry, platform)
            )
        else:
            task.cancel()
            tasks.append(task)

    unload_ok = all(await asyncio.gather(*tasks))

    if DATA_CLIENT_LISTEN_TASK in info:
        await disconnect_client(hass, entry)

    hass.data[DOMAIN].pop(entry.entry_id)

    if entry.data.get(CONF_USE_ADDON) and entry.disabled_by:
        addon_manager: AddonManager = get_addon_manager(hass)
        LOGGER.debug("Stopping Z-Wave JS add-on")
        try:
            await addon_manager.async_stop_addon()
        except AddonError as err:
            LOGGER.error("Failed to stop the Z-Wave JS add-on: %s", err)
            return False

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    if not entry.data.get(CONF_INTEGRATION_CREATED_ADDON):
        return

    addon_manager: AddonManager = get_addon_manager(hass)
    try:
        await addon_manager.async_stop_addon()
    except AddonError as err:
        LOGGER.error(err)
        return
    try:
        await addon_manager.async_create_backup()
    except AddonError as err:
        LOGGER.error(err)
        return
    try:
        await addon_manager.async_uninstall_addon()
    except AddonError as err:
        LOGGER.error(err)


async def async_ensure_addon_running(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ensure that Z-Wave JS add-on is installed and running."""
    addon_manager: AddonManager = get_addon_manager(hass)
    if addon_manager.task_in_progress():
        raise ConfigEntryNotReady
    try:
        addon_info = await addon_manager.async_get_addon_info()
    except AddonError as err:
        raise ConfigEntryNotReady(err) from err

    usb_path: str = entry.data[CONF_USB_PATH]
    # s0_legacy_key was saved as network_key before s2 was added.
    s0_legacy_key: str = entry.data.get(CONF_S0_LEGACY_KEY, "")
    if not s0_legacy_key:
        s0_legacy_key = entry.data.get(CONF_NETWORK_KEY, "")
    s2_access_control_key: str = entry.data.get(CONF_S2_ACCESS_CONTROL_KEY, "")
    s2_authenticated_key: str = entry.data.get(CONF_S2_AUTHENTICATED_KEY, "")
    s2_unauthenticated_key: str = entry.data.get(CONF_S2_UNAUTHENTICATED_KEY, "")
    addon_state = addon_info.state

    if addon_state == AddonState.NOT_INSTALLED:
        addon_manager.async_schedule_install_setup_addon(
            usb_path,
            s0_legacy_key,
            s2_access_control_key,
            s2_authenticated_key,
            s2_unauthenticated_key,
            catch_error=True,
        )
        raise ConfigEntryNotReady

    if addon_state == AddonState.NOT_RUNNING:
        addon_manager.async_schedule_setup_addon(
            usb_path,
            s0_legacy_key,
            s2_access_control_key,
            s2_authenticated_key,
            s2_unauthenticated_key,
            catch_error=True,
        )
        raise ConfigEntryNotReady

    addon_options = addon_info.options
    addon_device = addon_options[CONF_ADDON_DEVICE]
    # s0_legacy_key was saved as network_key before s2 was added.
    addon_s0_legacy_key = addon_options.get(CONF_ADDON_S0_LEGACY_KEY, "")
    if not addon_s0_legacy_key:
        addon_s0_legacy_key = addon_options.get(CONF_ADDON_NETWORK_KEY, "")
    addon_s2_access_control_key = addon_options.get(
        CONF_ADDON_S2_ACCESS_CONTROL_KEY, ""
    )
    addon_s2_authenticated_key = addon_options.get(CONF_ADDON_S2_AUTHENTICATED_KEY, "")
    addon_s2_unauthenticated_key = addon_options.get(
        CONF_ADDON_S2_UNAUTHENTICATED_KEY, ""
    )
    updates = {}
    if usb_path != addon_device:
        updates[CONF_USB_PATH] = addon_device
    if s0_legacy_key != addon_s0_legacy_key:
        updates[CONF_S0_LEGACY_KEY] = addon_s0_legacy_key
    if s2_access_control_key != addon_s2_access_control_key:
        updates[CONF_S2_ACCESS_CONTROL_KEY] = addon_s2_access_control_key
    if s2_authenticated_key != addon_s2_authenticated_key:
        updates[CONF_S2_AUTHENTICATED_KEY] = addon_s2_authenticated_key
    if s2_unauthenticated_key != addon_s2_unauthenticated_key:
        updates[CONF_S2_UNAUTHENTICATED_KEY] = addon_s2_unauthenticated_key
    if updates:
        hass.config_entries.async_update_entry(entry, data={**entry.data, **updates})


@callback
def async_ensure_addon_updated(hass: HomeAssistant) -> None:
    """Ensure that Z-Wave JS add-on is updated and running."""
    addon_manager: AddonManager = get_addon_manager(hass)
    if addon_manager.task_in_progress():
        raise ConfigEntryNotReady
    addon_manager.async_schedule_update_addon(catch_error=True)
