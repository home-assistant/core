"""Connect to a MySensors gateway via pymysensors API."""

from collections.abc import Mapping
import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import AnyDeviceEntry, DeviceEntry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_DEVICES, DOMAIN, PLATFORMS, DevId, DiscoveryInfo, SensorType
from .entity import MySensorsChildEntity
from .gateway import finish_setup, gw_stop, setup_gateway
from .helpers import remove_node_dev_ids
from .models import MySensorsConfigEntry, MySensorsData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: MySensorsConfigEntry) -> bool:
    """Set up an instance of the MySensors integration.

    Every instance has a connection to exactly one Gateway.
    """
    gateway = await setup_gateway(hass, entry)

    if not gateway:
        _LOGGER.error("Gateway setup failed for %s", entry.data)
        return False

    entry.runtime_data = MySensorsData(gateway=gateway)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await finish_setup(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MySensorsConfigEntry) -> bool:
    """Remove an instance of the MySensors integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    await gw_stop(entry)
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: MySensorsConfigEntry,
    device_entry: AnyDeviceEntry,
) -> bool:
    """Remove a MySensors config entry from a device."""
    if not isinstance(device_entry, DeviceEntry):
        # This integration does not create child devices.
        return False
    gateway = config_entry.runtime_data.gateway
    device_id = next(
        device_id for domain, device_id in device_entry.identifiers if domain == DOMAIN
    )
    node_id = int(device_id.partition("-")[2])
    gateway.sensors.pop(node_id, None)
    gateway.tasks.persistence.need_save = True

    # remove node from discovered nodes
    config_entry.runtime_data.discovered_nodes.discard(node_id)
    remove_node_dev_ids(config_entry, node_id)

    return True


@callback
def setup_mysensors_platform(
    config_entry: MySensorsConfigEntry,
    domain: Platform,  # hass platform name
    discovery_info: DiscoveryInfo,
    device_class: type[MySensorsChildEntity]
    | Mapping[SensorType, type[MySensorsChildEntity]],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for newly discovered devices on a MySensors platform."""
    new_devices: list[MySensorsChildEntity] = []
    new_dev_ids: list[DevId] = discovery_info[ATTR_DEVICES]
    dev_ids = config_entry.runtime_data.discovered_dev_ids[domain]
    gateway = config_entry.runtime_data.gateway
    for dev_id in new_dev_ids:
        if dev_id in dev_ids:
            _LOGGER.debug(
                "Skipping setup of %s for platform %s as it already exists",
                dev_id,
                domain,
            )
            continue
        _gateway_id, node_id, child_id, value_type = dev_id

        if isinstance(device_class, dict):
            child = gateway.sensors[node_id].children[child_id]
            s_type = gateway.const.Presentation(child.type).name
            device_class_copy = device_class[s_type]
        else:
            device_class_copy = device_class

        dev_ids.add(dev_id)
        new_devices.append(
            device_class_copy(config_entry, node_id, child_id, value_type)
        )
    if new_devices:
        _LOGGER.debug("Adding new devices: %s", new_devices)
        async_add_entities(new_devices)
