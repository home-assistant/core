"""Support for Z-Wave."""
# pylint: disable=import-outside-toplevel
import asyncio
import copy
from importlib import import_module
import logging
from pprint import pprint

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CoreState, callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import (
    async_get_registry as async_get_device_registry,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get_registry as async_get_entity_registry,
)
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import convert
import homeassistant.util.dt as dt_util

from . import const, websocket_api as wsapi, workaround
from .const import (
    CONF_AUTOHEAL,
    CONF_CONFIG_PATH,
    CONF_DEBUG,
    CONF_NETWORK_KEY,
    CONF_POLLING_INTERVAL,
    CONF_USB_STICK_PATH,
    DATA_DEVICES,
    DATA_ENTITY_VALUES,
    DATA_NETWORK,
    DATA_ZWAVE_CONFIG,
    DEFAULT_CONF_AUTOHEAL,
    DEFAULT_CONF_USB_STICK_PATH,
    DEFAULT_DEBUG,
    DEFAULT_POLLING_INTERVAL,
    DOMAIN,
)
from .discovery_schemas import DISCOVERY_SCHEMAS
from .node_entity import ZWaveBaseEntity, ZWaveNodeEntity
from .util import (
    check_has_unique_id,
    check_node_schema,
    check_value_schema,
    is_node_parsed,
    node_device_id_and_name,
    node_name,
)

_LOGGER = logging.getLogger(__name__)

CLASS_ID = "class_id"

ATTR_POWER = "power_consumption"

CONF_POLLING_INTENSITY = "polling_intensity"
CONF_IGNORED = "ignored"
CONF_INVERT_OPENCLOSE_BUTTONS = "invert_openclose_buttons"
CONF_INVERT_PERCENT = "invert_percent"
CONF_REFRESH_VALUE = "refresh_value"
CONF_REFRESH_DELAY = "delay"
CONF_DEVICE_CONFIG = "device_config"
CONF_DEVICE_CONFIG_GLOB = "device_config_glob"
CONF_DEVICE_CONFIG_DOMAIN = "device_config_domain"

DATA_ZWAVE_CONFIG_YAML_PRESENT = "zwave_config_yaml_present"

DEFAULT_CONF_IGNORED = False
DEFAULT_CONF_INVERT_OPENCLOSE_BUTTONS = False
DEFAULT_CONF_INVERT_PERCENT = False
DEFAULT_CONF_REFRESH_VALUE = False
DEFAULT_CONF_REFRESH_DELAY = 5

PLATFORMS = [
    "binary_sensor",
    "climate",
    "cover",
    "fan",
    "lock",
    "light",
    "sensor",
    "switch",
]

RENAME_NODE_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(const.ATTR_UPDATE_IDS, default=False): cv.boolean,
    }
)

RENAME_VALUE_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(const.ATTR_VALUE_ID): vol.Coerce(int),
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(const.ATTR_UPDATE_IDS, default=False): cv.boolean,
    }
)

SET_CONFIG_PARAMETER_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(const.ATTR_CONFIG_PARAMETER): vol.Coerce(int),
        vol.Required(const.ATTR_CONFIG_VALUE): vol.Any(vol.Coerce(int), cv.string),
        vol.Optional(const.ATTR_CONFIG_SIZE, default=2): vol.Coerce(int),
    }
)

SET_NODE_VALUE_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(const.ATTR_VALUE_ID): vol.Any(vol.Coerce(int), cv.string),
        vol.Required(const.ATTR_CONFIG_VALUE): vol.Any(vol.Coerce(int), cv.string),
    }
)

REFRESH_NODE_VALUE_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(const.ATTR_VALUE_ID): vol.Coerce(int),
    }
)

SET_POLL_INTENSITY_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(const.ATTR_VALUE_ID): vol.Coerce(int),
        vol.Required(const.ATTR_POLL_INTENSITY): vol.Coerce(int),
    }
)

PRINT_CONFIG_PARAMETER_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(const.ATTR_CONFIG_PARAMETER): vol.Coerce(int),
    }
)

NODE_SERVICE_SCHEMA = vol.Schema({vol.Required(const.ATTR_NODE_ID): vol.Coerce(int)})

REFRESH_ENTITY_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_id})

RESET_NODE_METERS_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Optional(const.ATTR_INSTANCE, default=1): vol.Coerce(int),
    }
)

CHANGE_ASSOCIATION_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_ASSOCIATION): cv.string,
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(const.ATTR_TARGET_NODE_ID): vol.Coerce(int),
        vol.Required(const.ATTR_GROUP): vol.Coerce(int),
        vol.Optional(const.ATTR_INSTANCE, default=0x00): vol.Coerce(int),
    }
)

SET_WAKEUP_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Required(const.ATTR_CONFIG_VALUE): vol.All(
            vol.Coerce(int), cv.positive_int
        ),
    }
)

HEAL_NODE_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Optional(const.ATTR_RETURN_ROUTES, default=False): cv.boolean,
    }
)

TEST_NODE_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
        vol.Optional(const.ATTR_MESSAGES, default=1): cv.positive_int,
    }
)


DEVICE_CONFIG_SCHEMA_ENTRY = vol.Schema(
    {
        vol.Optional(CONF_POLLING_INTENSITY): cv.positive_int,
        vol.Optional(CONF_IGNORED, default=DEFAULT_CONF_IGNORED): cv.boolean,
        vol.Optional(
            CONF_INVERT_OPENCLOSE_BUTTONS, default=DEFAULT_CONF_INVERT_OPENCLOSE_BUTTONS
        ): cv.boolean,
        vol.Optional(
            CONF_INVERT_PERCENT, default=DEFAULT_CONF_INVERT_PERCENT
        ): cv.boolean,
        vol.Optional(
            CONF_REFRESH_VALUE, default=DEFAULT_CONF_REFRESH_VALUE
        ): cv.boolean,
        vol.Optional(
            CONF_REFRESH_DELAY, default=DEFAULT_CONF_REFRESH_DELAY
        ): cv.positive_int,
    }
)

SIGNAL_REFRESH_ENTITY_FORMAT = "zwave_refresh_entity_{}"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_AUTOHEAL, default=DEFAULT_CONF_AUTOHEAL): cv.boolean,
                vol.Optional(CONF_CONFIG_PATH): cv.string,
                vol.Optional(CONF_NETWORK_KEY): vol.All(
                    cv.string, vol.Match(r"(0x\w\w,\s?){15}0x\w\w")
                ),
                vol.Optional(CONF_DEVICE_CONFIG, default={}): vol.Schema(
                    {cv.entity_id: DEVICE_CONFIG_SCHEMA_ENTRY}
                ),
                vol.Optional(CONF_DEVICE_CONFIG_GLOB, default={}): vol.Schema(
                    {cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}
                ),
                vol.Optional(CONF_DEVICE_CONFIG_DOMAIN, default={}): vol.Schema(
                    {cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}
                ),
                vol.Optional(CONF_DEBUG, default=DEFAULT_DEBUG): cv.boolean,
                vol.Optional(
                    CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL
                ): cv.positive_int,
                vol.Optional(CONF_USB_STICK_PATH): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_get_ozw_migration_data(hass):
    """Return dict with info for migration to ozw integration."""
    data_to_migrate = {}

    zwave_config_entries = hass.config_entries.async_entries(DOMAIN)
    if not zwave_config_entries:
        _LOGGER.error("Config entry not set up")
        return data_to_migrate

    if hass.data.get(DATA_ZWAVE_CONFIG_YAML_PRESENT):
        _LOGGER.warning(
            "Remove %s from configuration.yaml "
            "to avoid setting up this integration on restart "
            "after completing migration to ozw",
            DOMAIN,
        )

    config_entry = zwave_config_entries[0]  # zwave only has a single config entry
    ent_reg = await async_get_entity_registry(hass)
    entity_entries = async_entries_for_config_entry(ent_reg, config_entry.entry_id)
    unique_entries = {entry.unique_id: entry for entry in entity_entries}
    dev_reg = await async_get_device_registry(hass)

    for entity_values in hass.data[DATA_ENTITY_VALUES]:
        node = entity_values.primary.node
        unique_id = compute_value_unique_id(node, entity_values.primary)
        if unique_id not in unique_entries:
            continue
        device_identifier, _ = node_device_id_and_name(
            node, entity_values.primary.instance
        )
        device_entry = dev_reg.async_get_device({device_identifier}, set())
        data_to_migrate[unique_id] = {
            "node_id": node.node_id,
            "node_instance": entity_values.primary.instance,
            "device_id": device_entry.id,
            "command_class": entity_values.primary.command_class,
            "command_class_label": entity_values.primary.label,
            "value_index": entity_values.primary.index,
            "unique_id": unique_id,
            "entity_entry": unique_entries[unique_id],
        }

    return data_to_migrate


@callback
def async_is_ozw_migrated(hass):
    """Return True if migration to ozw is done."""
    ozw_config_entries = hass.config_entries.async_entries("ozw")
    if not ozw_config_entries:
        return False

    ozw_config_entry = ozw_config_entries[0]  # only one ozw entry is allowed
    migrated = bool(ozw_config_entry.data.get("migrated"))
    return migrated


def _obj_to_dict(obj):
    """Convert an object into a hash for debug."""
    return {
        key: getattr(obj, key)
        for key in dir(obj)
        if key[0] != "_" and not callable(getattr(obj, key))
    }


def _value_name(value):
    """Return the name of the value."""
    return f"{node_name(value.node)} {value.label}".strip()


def nice_print_node(node):
    """Print a nice formatted node to the output (debug method)."""
    node_dict = _obj_to_dict(node)
    node_dict["values"] = {
        value_id: _obj_to_dict(value) for value_id, value in node.values.items()
    }

    _LOGGER.info("FOUND NODE %s \n%s", node.product_name, node_dict)


def get_config_value(node, value_index, tries=5):
    """Return the current configuration value for a specific index."""
    try:
        for value in node.values.values():
            if (
                value.command_class == const.COMMAND_CLASS_CONFIGURATION
                and value.index == value_index
            ):
                return value.data
    except RuntimeError:
        # If we get a runtime error the dict has changed while
        # we was looking for a value, just do it again
        return (
            None if tries <= 0 else get_config_value(node, value_index, tries=tries - 1)
        )
    return None


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Z-Wave platform (generic part)."""
    if discovery_info is None or DATA_NETWORK not in hass.data:
        return False

    device = hass.data[DATA_DEVICES].get(discovery_info[const.DISCOVERY_DEVICE])
    if device is None:
        return False

    async_add_entities([device])
    return True


async def async_setup(hass, config):
    """Set up Z-Wave components."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    hass.data[DATA_ZWAVE_CONFIG] = conf
    hass.data[DATA_ZWAVE_CONFIG_YAML_PRESENT] = True

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={
                    CONF_USB_STICK_PATH: conf.get(
                        CONF_USB_STICK_PATH, DEFAULT_CONF_USB_STICK_PATH
                    ),
                    CONF_NETWORK_KEY: conf.get(CONF_NETWORK_KEY),
                },
            )
        )

    return True


async def async_setup_entry(hass, config_entry):  # noqa: C901
    """Set up Z-Wave from a config entry.

    Will automatically load components to support devices found on the network.
    """
    from openzwave.group import ZWaveGroup
    from openzwave.network import ZWaveNetwork
    from openzwave.option import ZWaveOption

    # pylint: enable=import-error
    from pydispatch import dispatcher

    if async_is_ozw_migrated(hass):
        _LOGGER.error(
            "Migration to ozw has been done. Please remove the zwave integration"
        )
        return False

    # Merge config entry and yaml config
    config = config_entry.data
    if DATA_ZWAVE_CONFIG in hass.data:
        config = {**config, **hass.data[DATA_ZWAVE_CONFIG]}

    # Update hass.data with merged config so we can access it elsewhere
    hass.data[DATA_ZWAVE_CONFIG] = config

    # Load configuration
    use_debug = config.get(CONF_DEBUG, DEFAULT_DEBUG)
    autoheal = config.get(CONF_AUTOHEAL, DEFAULT_CONF_AUTOHEAL)
    device_config = EntityValues(
        config.get(CONF_DEVICE_CONFIG),
        config.get(CONF_DEVICE_CONFIG_DOMAIN),
        config.get(CONF_DEVICE_CONFIG_GLOB),
    )

    usb_path = config[CONF_USB_STICK_PATH]

    _LOGGER.info("Z-Wave USB path is %s", usb_path)

    # Setup options
    options = ZWaveOption(
        usb_path,
        user_path=hass.config.config_dir,
        config_path=config.get(CONF_CONFIG_PATH),
    )

    options.set_console_output(use_debug)

    if config.get(CONF_NETWORK_KEY):
        options.addOption("NetworkKey", config[CONF_NETWORK_KEY])

    await hass.async_add_executor_job(options.lock)
    network = hass.data[DATA_NETWORK] = ZWaveNetwork(options, autostart=False)
    hass.data[DATA_DEVICES] = {}
    hass.data[DATA_ENTITY_VALUES] = []

    registry = await async_get_entity_registry(hass)

    wsapi.async_load_websocket_api(hass)

    if use_debug:  # pragma: no cover

        def log_all(signal, value=None):
            """Log all the signals."""
            print("")
            print("SIGNAL *****", signal)
            if value and signal in (
                ZWaveNetwork.SIGNAL_VALUE_CHANGED,
                ZWaveNetwork.SIGNAL_VALUE_ADDED,
                ZWaveNetwork.SIGNAL_SCENE_EVENT,
                ZWaveNetwork.SIGNAL_NODE_EVENT,
                ZWaveNetwork.SIGNAL_AWAKE_NODES_QUERIED,
                ZWaveNetwork.SIGNAL_ALL_NODES_QUERIED,
                ZWaveNetwork.SIGNAL_ALL_NODES_QUERIED_SOME_DEAD,
            ):
                pprint(_obj_to_dict(value))

            print("")

        dispatcher.connect(log_all, weak=False)

    def value_added(node, value):
        """Handle new added value to a node on the network."""
        # Check if this value should be tracked by an existing entity
        for values in hass.data[DATA_ENTITY_VALUES]:
            values.check_value(value)

        for schema in DISCOVERY_SCHEMAS:
            if not check_node_schema(node, schema):
                continue
            if not check_value_schema(
                value, schema[const.DISC_VALUES][const.DISC_PRIMARY]
            ):
                continue

            values = ZWaveDeviceEntityValues(
                hass, schema, value, config, device_config, registry
            )

            # We create a new list and update the reference here so that
            # the list can be safely iterated over in the main thread
            new_values = hass.data[DATA_ENTITY_VALUES] + [values]
            hass.data[DATA_ENTITY_VALUES] = new_values

    platform = EntityPlatform(
        hass=hass,
        logger=_LOGGER,
        domain=DOMAIN,
        platform_name=DOMAIN,
        platform=None,
        scan_interval=DEFAULT_SCAN_INTERVAL,
        entity_namespace=None,
    )
    platform.config_entry = config_entry

    def node_added(node):
        """Handle a new node on the network."""
        entity = ZWaveNodeEntity(node, network)

        async def _add_node_to_component():
            if hass.data[DATA_DEVICES].get(entity.unique_id):
                return

            name = node_name(node)
            generated_id = generate_entity_id(DOMAIN + ".{}", name, [])
            node_config = device_config.get(generated_id)
            if node_config.get(CONF_IGNORED):
                _LOGGER.info(
                    "Ignoring node entity %s due to device settings", generated_id
                )
                return

            hass.data[DATA_DEVICES][entity.unique_id] = entity
            await platform.async_add_entities([entity])

        if entity.unique_id:
            hass.async_add_job(_add_node_to_component())
            return

        @callback
        def _on_ready(sec):
            _LOGGER.info("Z-Wave node %d ready after %d seconds", entity.node_id, sec)
            hass.async_add_job(_add_node_to_component)

        @callback
        def _on_timeout(sec):
            _LOGGER.warning(
                "Z-Wave node %d not ready after %d seconds, continuing anyway",
                entity.node_id,
                sec,
            )
            hass.async_add_job(_add_node_to_component)

        hass.add_job(check_has_unique_id, entity, _on_ready, _on_timeout)

    def node_removed(node):
        node_id = node.node_id
        node_key = f"node-{node_id}"
        for key in list(hass.data[DATA_DEVICES]):
            if key is None:
                continue
            if not key.startswith(f"{node_id}-"):
                continue

            entity = hass.data[DATA_DEVICES][key]
            _LOGGER.debug(
                "Removing Entity - value: %s - entity_id: %s", key, entity.entity_id
            )
            hass.add_job(entity.node_removed())
            del hass.data[DATA_DEVICES][key]

        entity = hass.data[DATA_DEVICES][node_key]
        hass.add_job(entity.node_removed())
        del hass.data[DATA_DEVICES][node_key]

        hass.add_job(_remove_device(node))

    async def _remove_device(node):
        dev_reg = await async_get_device_registry(hass)
        identifier, name = node_device_id_and_name(node)
        device = dev_reg.async_get_device(identifiers={identifier})
        if device is not None:
            _LOGGER.debug("Removing Device - %s - %s", device.id, name)
            dev_reg.async_remove_device(device.id)

    def network_ready():
        """Handle the query of all awake nodes."""
        _LOGGER.info(
            "Z-Wave network is ready for use. All awake nodes "
            "have been queried. Sleeping nodes will be "
            "queried when they awake"
        )
        hass.bus.fire(const.EVENT_NETWORK_READY)

    def network_complete():
        """Handle the querying of all nodes on network."""
        _LOGGER.info(
            "Z-Wave network is complete. All nodes on the network have been queried"
        )
        hass.bus.fire(const.EVENT_NETWORK_COMPLETE)

    def network_complete_some_dead():
        """Handle the querying of all nodes on network."""
        _LOGGER.info(
            "Z-Wave network is complete. All nodes on the network "
            "have been queried, but some nodes are marked dead"
        )
        hass.bus.fire(const.EVENT_NETWORK_COMPLETE_SOME_DEAD)

    dispatcher.connect(value_added, ZWaveNetwork.SIGNAL_VALUE_ADDED, weak=False)
    dispatcher.connect(node_added, ZWaveNetwork.SIGNAL_NODE_ADDED, weak=False)
    dispatcher.connect(node_removed, ZWaveNetwork.SIGNAL_NODE_REMOVED, weak=False)
    dispatcher.connect(
        network_ready, ZWaveNetwork.SIGNAL_AWAKE_NODES_QUERIED, weak=False
    )
    dispatcher.connect(
        network_complete, ZWaveNetwork.SIGNAL_ALL_NODES_QUERIED, weak=False
    )
    dispatcher.connect(
        network_complete_some_dead,
        ZWaveNetwork.SIGNAL_ALL_NODES_QUERIED_SOME_DEAD,
        weak=False,
    )

    def add_node(service):
        """Switch into inclusion mode."""
        _LOGGER.info("Z-Wave add_node have been initialized")
        network.controller.add_node()

    def add_node_secure(service):
        """Switch into secure inclusion mode."""
        _LOGGER.info("Z-Wave add_node_secure have been initialized")
        network.controller.add_node(True)

    def remove_node(service):
        """Switch into exclusion mode."""
        _LOGGER.info("Z-Wave remove_node have been initialized")
        network.controller.remove_node()

    def cancel_command(service):
        """Cancel a running controller command."""
        _LOGGER.info("Cancel running Z-Wave command")
        network.controller.cancel_command()

    def heal_network(service):
        """Heal the network."""
        _LOGGER.info("Z-Wave heal running")
        network.heal()

    def soft_reset(service):
        """Soft reset the controller."""
        _LOGGER.info("Z-Wave soft_reset have been initialized")
        network.controller.soft_reset()

    def test_network(service):
        """Test the network by sending commands to all the nodes."""
        _LOGGER.info("Z-Wave test_network have been initialized")
        network.test()

    def stop_network(_service_or_event):
        """Stop Z-Wave network."""
        _LOGGER.info("Stopping Z-Wave network")
        network.stop()
        if hass.state == CoreState.running:
            hass.bus.fire(const.EVENT_NETWORK_STOP)

    async def rename_node(service):
        """Rename a node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        name = service.data.get(ATTR_NAME)
        node.name = name
        _LOGGER.info("Renamed Z-Wave node %d to %s", node_id, name)
        update_ids = service.data.get(const.ATTR_UPDATE_IDS)
        # We want to rename the device, the node entity,
        # and all the contained entities
        node_key = f"node-{node_id}"
        entity = hass.data[DATA_DEVICES][node_key]
        await entity.node_renamed(update_ids)
        for key in list(hass.data[DATA_DEVICES]):
            if not key.startswith(f"{node_id}-"):
                continue
            entity = hass.data[DATA_DEVICES][key]
            await entity.value_renamed(update_ids)

    async def rename_value(service):
        """Rename a node value."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        value_id = service.data.get(const.ATTR_VALUE_ID)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        value = node.values[value_id]
        name = service.data.get(ATTR_NAME)
        value.label = name
        _LOGGER.info(
            "Renamed Z-Wave value (Node %d Value %d) to %s", node_id, value_id, name
        )
        update_ids = service.data.get(const.ATTR_UPDATE_IDS)
        value_key = f"{node_id}-{value_id}"
        entity = hass.data[DATA_DEVICES][value_key]
        await entity.value_renamed(update_ids)

    def set_poll_intensity(service):
        """Set the polling intensity of a node value."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        value_id = service.data.get(const.ATTR_VALUE_ID)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        value = node.values[value_id]
        intensity = service.data.get(const.ATTR_POLL_INTENSITY)
        if intensity == 0:
            if value.disable_poll():
                _LOGGER.info("Polling disabled (Node %d Value %d)", node_id, value_id)
                return
            _LOGGER.info(
                "Polling disabled failed (Node %d Value %d)", node_id, value_id
            )
        else:
            if value.enable_poll(intensity):
                _LOGGER.info(
                    "Set polling intensity (Node %d Value %d) to %s",
                    node_id,
                    value_id,
                    intensity,
                )
                return
            _LOGGER.info(
                "Set polling intensity failed (Node %d Value %d)", node_id, value_id
            )

    def remove_failed_node(service):
        """Remove failed node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        _LOGGER.info("Trying to remove zwave node %d", node_id)
        network.controller.remove_failed_node(node_id)

    def replace_failed_node(service):
        """Replace failed node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        _LOGGER.info("Trying to replace zwave node %d", node_id)
        network.controller.replace_failed_node(node_id)

    def set_config_parameter(service):
        """Set a config parameter to a node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        param = service.data.get(const.ATTR_CONFIG_PARAMETER)
        selection = service.data.get(const.ATTR_CONFIG_VALUE)
        size = service.data.get(const.ATTR_CONFIG_SIZE)
        for value in node.get_values(
            class_id=const.COMMAND_CLASS_CONFIGURATION
        ).values():
            if value.index != param:
                continue
            if value.type == const.TYPE_BOOL:
                value.data = int(selection == "True")
                _LOGGER.info(
                    "Setting configuration parameter %s on Node %s with bool selection %s",
                    param,
                    node_id,
                    str(selection),
                )
                return
            if value.type == const.TYPE_LIST:
                value.data = str(selection)
                _LOGGER.info(
                    "Setting configuration parameter %s on Node %s with list selection %s",
                    param,
                    node_id,
                    str(selection),
                )
                return
            if value.type == const.TYPE_BUTTON:
                network.manager.pressButton(value.value_id)
                network.manager.releaseButton(value.value_id)
                _LOGGER.info(
                    "Setting configuration parameter %s on Node %s "
                    "with button selection %s",
                    param,
                    node_id,
                    selection,
                )
                return
            value.data = int(selection)
            _LOGGER.info(
                "Setting configuration parameter %s on Node %s with selection %s",
                param,
                node_id,
                selection,
            )
            return
        node.set_config_param(param, selection, size)
        _LOGGER.info(
            "Setting unknown configuration parameter %s on Node %s with selection %s",
            param,
            node_id,
            selection,
        )

    def refresh_node_value(service):
        """Refresh the specified value from a node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        value_id = service.data.get(const.ATTR_VALUE_ID)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        node.values[value_id].refresh()
        _LOGGER.info("Node %s value %s refreshed", node_id, value_id)

    def set_node_value(service):
        """Set the specified value on a node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        value_id = service.data.get(const.ATTR_VALUE_ID)
        value = service.data.get(const.ATTR_CONFIG_VALUE)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        node.values[value_id].data = value
        _LOGGER.info("Node %s value %s set to %s", node_id, value_id, value)

    def print_config_parameter(service):
        """Print a config parameter from a node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        param = service.data.get(const.ATTR_CONFIG_PARAMETER)
        _LOGGER.info(
            "Config parameter %s on Node %s: %s",
            param,
            node_id,
            get_config_value(node, param),
        )

    def print_node(service):
        """Print all information about z-wave node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        nice_print_node(node)

    def set_wakeup(service):
        """Set wake-up interval of a node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        value = service.data.get(const.ATTR_CONFIG_VALUE)
        if node.can_wake_up():
            for value_id in node.get_values(class_id=const.COMMAND_CLASS_WAKE_UP):
                node.values[value_id].data = value
                _LOGGER.info("Node %s wake-up set to %d", node_id, value)
        else:
            _LOGGER.info("Node %s is not wakeable", node_id)

    def change_association(service):
        """Change an association in the zwave network."""
        association_type = service.data.get(const.ATTR_ASSOCIATION)
        node_id = service.data.get(const.ATTR_NODE_ID)
        target_node_id = service.data.get(const.ATTR_TARGET_NODE_ID)
        group = service.data.get(const.ATTR_GROUP)
        instance = service.data.get(const.ATTR_INSTANCE)

        node = ZWaveGroup(group, network, node_id)
        if association_type == "add":
            node.add_association(target_node_id, instance)
            _LOGGER.info(
                "Adding association for node:%s in group:%s "
                "target node:%s, instance=%s",
                node_id,
                group,
                target_node_id,
                instance,
            )
        if association_type == "remove":
            node.remove_association(target_node_id, instance)
            _LOGGER.info(
                "Removing association for node:%s in group:%s "
                "target node:%s, instance=%s",
                node_id,
                group,
                target_node_id,
                instance,
            )

    async def async_refresh_entity(service):
        """Refresh values that specific entity depends on."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        async_dispatcher_send(hass, SIGNAL_REFRESH_ENTITY_FORMAT.format(entity_id))

    def refresh_node(service):
        """Refresh all node info."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        node.refresh_info()

    def reset_node_meters(service):
        """Reset meter counters of a node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        instance = service.data.get(const.ATTR_INSTANCE)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        for value in node.get_values(class_id=const.COMMAND_CLASS_METER).values():
            if value.index != const.INDEX_METER_RESET:
                continue
            if value.instance != instance:
                continue
            network.manager.pressButton(value.value_id)
            network.manager.releaseButton(value.value_id)
            _LOGGER.info("Resetting meters on node %s instance %s", node_id, instance)
            return
        _LOGGER.info(
            "Node %s on instance %s does not have resettable meters", node_id, instance
        )

    def heal_node(service):
        """Heal a node on the network."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        update_return_routes = service.data.get(const.ATTR_RETURN_ROUTES)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        _LOGGER.info("Z-Wave node heal running for node %s", node_id)
        node.heal(update_return_routes)

    def test_node(service):
        """Send test messages to a node on the network."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        messages = service.data.get(const.ATTR_MESSAGES)
        node = network.nodes[node_id]  # pylint: disable=unsubscriptable-object
        _LOGGER.info("Sending %s test-messages to node %s", messages, node_id)
        node.test(messages)

    def start_zwave(_service_or_event):
        """Startup Z-Wave network."""
        _LOGGER.info("Starting Z-Wave network")
        network.start()
        hass.bus.fire(const.EVENT_NETWORK_START)

        async def _check_awaked():
            """Wait for Z-wave awaked state (or timeout) and finalize start."""
            _LOGGER.debug("network state: %d %s", network.state, network.state_str)

            start_time = dt_util.utcnow()
            while True:
                waited = int((dt_util.utcnow() - start_time).total_seconds())

                if network.state >= network.STATE_AWAKED:
                    # Need to be in STATE_AWAKED before talking to nodes.
                    _LOGGER.info("Z-Wave ready after %d seconds", waited)
                    break

                if waited >= const.NETWORK_READY_WAIT_SECS:
                    # Wait up to NETWORK_READY_WAIT_SECS seconds for the Z-Wave
                    # network to be ready.
                    _LOGGER.warning(
                        "Z-Wave not ready after %d seconds, continuing anyway", waited
                    )
                    _LOGGER.info(
                        "Final network state: %d %s", network.state, network.state_str
                    )
                    break

                await asyncio.sleep(1)

            hass.async_add_job(_finalize_start)

        hass.add_job(_check_awaked)

    def _finalize_start():
        """Perform final initializations after Z-Wave network is awaked."""
        polling_interval = convert(config.get(CONF_POLLING_INTERVAL), int)
        if polling_interval is not None:
            network.set_poll_interval(polling_interval, False)

        poll_interval = network.get_poll_interval()
        _LOGGER.info("Z-Wave polling interval set to %d ms", poll_interval)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_network)

        # Register node services for Z-Wave network
        hass.services.register(DOMAIN, const.SERVICE_ADD_NODE, add_node)
        hass.services.register(DOMAIN, const.SERVICE_ADD_NODE_SECURE, add_node_secure)
        hass.services.register(DOMAIN, const.SERVICE_REMOVE_NODE, remove_node)
        hass.services.register(DOMAIN, const.SERVICE_CANCEL_COMMAND, cancel_command)
        hass.services.register(DOMAIN, const.SERVICE_HEAL_NETWORK, heal_network)
        hass.services.register(DOMAIN, const.SERVICE_SOFT_RESET, soft_reset)
        hass.services.register(DOMAIN, const.SERVICE_TEST_NETWORK, test_network)
        hass.services.register(DOMAIN, const.SERVICE_STOP_NETWORK, stop_network)
        hass.services.register(
            DOMAIN, const.SERVICE_RENAME_NODE, rename_node, schema=RENAME_NODE_SCHEMA
        )
        hass.services.register(
            DOMAIN, const.SERVICE_RENAME_VALUE, rename_value, schema=RENAME_VALUE_SCHEMA
        )
        hass.services.register(
            DOMAIN,
            const.SERVICE_SET_CONFIG_PARAMETER,
            set_config_parameter,
            schema=SET_CONFIG_PARAMETER_SCHEMA,
        )
        hass.services.register(
            DOMAIN,
            const.SERVICE_SET_NODE_VALUE,
            set_node_value,
            schema=SET_NODE_VALUE_SCHEMA,
        )
        hass.services.register(
            DOMAIN,
            const.SERVICE_REFRESH_NODE_VALUE,
            refresh_node_value,
            schema=REFRESH_NODE_VALUE_SCHEMA,
        )
        hass.services.register(
            DOMAIN,
            const.SERVICE_PRINT_CONFIG_PARAMETER,
            print_config_parameter,
            schema=PRINT_CONFIG_PARAMETER_SCHEMA,
        )
        hass.services.register(
            DOMAIN,
            const.SERVICE_REMOVE_FAILED_NODE,
            remove_failed_node,
            schema=NODE_SERVICE_SCHEMA,
        )
        hass.services.register(
            DOMAIN,
            const.SERVICE_REPLACE_FAILED_NODE,
            replace_failed_node,
            schema=NODE_SERVICE_SCHEMA,
        )

        hass.services.register(
            DOMAIN,
            const.SERVICE_CHANGE_ASSOCIATION,
            change_association,
            schema=CHANGE_ASSOCIATION_SCHEMA,
        )
        hass.services.register(
            DOMAIN, const.SERVICE_SET_WAKEUP, set_wakeup, schema=SET_WAKEUP_SCHEMA
        )
        hass.services.register(
            DOMAIN, const.SERVICE_PRINT_NODE, print_node, schema=NODE_SERVICE_SCHEMA
        )
        hass.services.register(
            DOMAIN,
            const.SERVICE_REFRESH_ENTITY,
            async_refresh_entity,
            schema=REFRESH_ENTITY_SCHEMA,
        )
        hass.services.register(
            DOMAIN, const.SERVICE_REFRESH_NODE, refresh_node, schema=NODE_SERVICE_SCHEMA
        )
        hass.services.register(
            DOMAIN,
            const.SERVICE_RESET_NODE_METERS,
            reset_node_meters,
            schema=RESET_NODE_METERS_SCHEMA,
        )
        hass.services.register(
            DOMAIN,
            const.SERVICE_SET_POLL_INTENSITY,
            set_poll_intensity,
            schema=SET_POLL_INTENSITY_SCHEMA,
        )
        hass.services.register(
            DOMAIN, const.SERVICE_HEAL_NODE, heal_node, schema=HEAL_NODE_SCHEMA
        )
        hass.services.register(
            DOMAIN, const.SERVICE_TEST_NODE, test_node, schema=TEST_NODE_SCHEMA
        )

    # Setup autoheal
    if autoheal:
        _LOGGER.info("Z-Wave network autoheal is enabled")
        async_track_time_change(hass, heal_network, hour=0, minute=0, second=0)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_zwave)

    hass.services.async_register(DOMAIN, const.SERVICE_START_NETWORK, start_zwave)

    for entry_component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, entry_component)
        )

    return True


class ZWaveDeviceEntityValues:
    """Manages entity access to the underlying zwave value objects."""

    def __init__(
        self, hass, schema, primary_value, zwave_config, device_config, registry
    ):
        """Initialize the values object with the passed entity schema."""
        self._hass = hass
        self._zwave_config = zwave_config
        self._device_config = device_config
        self._schema = copy.deepcopy(schema)
        self._values = {}
        self._entity = None
        self._workaround_ignore = False
        self._registry = registry

        for name in self._schema[const.DISC_VALUES].keys():
            self._values[name] = None
            self._schema[const.DISC_VALUES][name][const.DISC_INSTANCE] = [
                primary_value.instance
            ]

        self._values[const.DISC_PRIMARY] = primary_value
        self._node = primary_value.node
        self._schema[const.DISC_NODE_ID] = [self._node.node_id]

        # Check values that have already been discovered for node
        for value in self._node.values.values():
            self.check_value(value)

        self._check_entity_ready()

    def __getattr__(self, name):
        """Get the specified value for this entity."""
        return self._values[name]

    def __iter__(self):
        """Allow iteration over all values."""
        return iter(self._values.values())

    def check_value(self, value):
        """Check if the new value matches a missing value for this entity.

        If a match is found, it is added to the values mapping.
        """
        if not check_node_schema(value.node, self._schema):
            return
        for name in self._values:
            if self._values[name] is not None:
                continue
            if not check_value_schema(value, self._schema[const.DISC_VALUES][name]):
                continue
            self._values[name] = value
            if self._entity:
                self._entity.value_added()
                self._entity.value_changed()

            self._check_entity_ready()

    def _check_entity_ready(self):
        """Check if all required values are discovered and create entity."""
        if self._workaround_ignore:
            return
        if self._entity is not None:
            return

        for name in self._schema[const.DISC_VALUES]:
            if self._values[name] is None and not self._schema[const.DISC_VALUES][
                name
            ].get(const.DISC_OPTIONAL):
                return

        component = self._schema[const.DISC_COMPONENT]

        workaround_component = workaround.get_device_component_mapping(self.primary)
        if workaround_component and workaround_component != component:
            if workaround_component == workaround.WORKAROUND_IGNORE:
                _LOGGER.info(
                    "Ignoring Node %d Value %d due to workaround",
                    self.primary.node.node_id,
                    self.primary.value_id,
                )
                # No entity will be created for this value
                self._workaround_ignore = True
                return
            _LOGGER.debug("Using %s instead of %s", workaround_component, component)
            component = workaround_component

        entity_id = self._registry.async_get_entity_id(
            component, DOMAIN, compute_value_unique_id(self._node, self.primary)
        )
        if entity_id is None:
            value_name = _value_name(self.primary)
            entity_id = generate_entity_id(component + ".{}", value_name, [])
        node_config = self._device_config.get(entity_id)

        # Configure node
        _LOGGER.debug(
            "Adding Node_id=%s Generic_command_class=%s, "
            "Specific_command_class=%s, "
            "Command_class=%s, Value type=%s, "
            "Genre=%s as %s",
            self._node.node_id,
            self._node.generic,
            self._node.specific,
            self.primary.command_class,
            self.primary.type,
            self.primary.genre,
            component,
        )

        if node_config.get(CONF_IGNORED):
            _LOGGER.info("Ignoring entity %s due to device settings", entity_id)
            # No entity will be created for this value
            self._workaround_ignore = True
            return

        polling_intensity = convert(node_config.get(CONF_POLLING_INTENSITY), int)
        if polling_intensity:
            self.primary.enable_poll(polling_intensity)

        platform = import_module(f".{component}", __name__)

        device = platform.get_device(
            node=self._node, values=self, node_config=node_config, hass=self._hass
        )
        if device is None:
            # No entity will be created for this value
            self._workaround_ignore = True
            return

        self._entity = device

        @callback
        def _on_ready(sec):
            _LOGGER.info(
                "Z-Wave entity %s (node_id: %d) ready after %d seconds",
                device.name,
                self._node.node_id,
                sec,
            )
            self._hass.async_add_job(discover_device, component, device)

        @callback
        def _on_timeout(sec):
            _LOGGER.warning(
                "Z-Wave entity %s (node_id: %d) not ready after %d seconds, "
                "continuing anyway",
                device.name,
                self._node.node_id,
                sec,
            )
            self._hass.async_add_job(discover_device, component, device)

        async def discover_device(component, device):
            """Put device in a dictionary and call discovery on it."""
            if self._hass.data[DATA_DEVICES].get(device.unique_id):
                return

            self._hass.data[DATA_DEVICES][device.unique_id] = device
            if component in PLATFORMS:
                async_dispatcher_send(self._hass, f"zwave_new_{component}", device)
            else:
                await discovery.async_load_platform(
                    self._hass,
                    component,
                    DOMAIN,
                    {const.DISCOVERY_DEVICE: device.unique_id},
                    self._zwave_config,
                )

        if device.unique_id:
            self._hass.add_job(discover_device, component, device)
        else:
            self._hass.add_job(check_has_unique_id, device, _on_ready, _on_timeout)


class ZWaveDeviceEntity(ZWaveBaseEntity):
    """Representation of a Z-Wave node entity."""

    def __init__(self, values, domain):
        """Initialize the z-Wave device."""
        super().__init__()
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher

        self.values = values
        self.node = values.primary.node
        self.values.primary.set_change_verified(False)

        self._name = _value_name(self.values.primary)
        self._unique_id = self._compute_unique_id()
        self._update_attributes()

        dispatcher.connect(
            self.network_value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED
        )

    def network_value_changed(self, value):
        """Handle a value change on the network."""
        if value.value_id in [v.value_id for v in self.values if v]:
            return self.value_changed()

    def value_added(self):
        """Handle a new value of this entity."""

    def value_changed(self):
        """Handle a changed value for this entity's node."""
        self._update_attributes()
        self.update_properties()
        self.maybe_schedule_update()

    async def value_renamed(self, update_ids=False):
        """Rename the node and update any IDs."""
        self._name = _value_name(self.values.primary)
        if update_ids:
            # Update entity ID.
            ent_reg = await async_get_entity_registry(self.hass)
            new_entity_id = ent_reg.async_generate_entity_id(
                self.platform.domain,
                self._name,
                self.platform.entities.keys() - {self.entity_id},
            )
            if new_entity_id != self.entity_id:
                # Don't change the name attribute, it will be None unless
                # customised and if it's been customised, keep the
                # customisation.
                ent_reg.async_update_entity(self.entity_id, new_entity_id=new_entity_id)
                return
        # else for the above two ifs, update if not using update_entity
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Add device to dict."""
        async_dispatcher_connect(
            self.hass,
            SIGNAL_REFRESH_ENTITY_FORMAT.format(self.entity_id),
            self.refresh_from_network,
        )

    def _update_attributes(self):
        """Update the node attributes. May only be used inside callback."""
        self.node_id = self.node.node_id
        self._name = _value_name(self.values.primary)
        if not self._unique_id:
            self._unique_id = self._compute_unique_id()
            if self._unique_id:
                self.try_remove_and_add()

        if self.values.power:
            self.power_consumption = round(
                self.values.power.data, self.values.power.precision
            )
        else:
            self.power_consumption = None

    def update_properties(self):
        """Update on data changes for node values."""

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        identifier, name = node_device_id_and_name(
            self.node, self.values.primary.instance
        )
        info = {
            "name": name,
            "identifiers": {identifier},
            "manufacturer": self.node.manufacturer_name,
            "model": self.node.product_name,
        }
        if self.values.primary.instance > 1:
            info["via_device"] = (DOMAIN, self.node_id)
        elif self.node_id > 1:
            info["via_device"] = (DOMAIN, 1)
        return info

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        attrs = {
            const.ATTR_NODE_ID: self.node_id,
            const.ATTR_VALUE_INDEX: self.values.primary.index,
            const.ATTR_VALUE_INSTANCE: self.values.primary.instance,
            const.ATTR_VALUE_ID: str(self.values.primary.value_id),
        }

        if self.power_consumption is not None:
            attrs[ATTR_POWER] = self.power_consumption

        return attrs

    def refresh_from_network(self):
        """Refresh all dependent values from zwave network."""
        for value in self.values:
            if value is not None:
                self.node.refresh_value(value.value_id)

    def _compute_unique_id(self):
        if (
            is_node_parsed(self.node) and self.values.primary.label != "Unknown"
        ) or self.node.is_ready:
            return compute_value_unique_id(self.node, self.values.primary)
        return None


def compute_value_unique_id(node, value):
    """Compute unique_id a value would get if it were to get one."""
    return f"{node.node_id}-{value.object_id}"
