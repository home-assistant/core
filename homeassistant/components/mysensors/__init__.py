"""Connect to a MySensors gateway via pymysensors API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging

from mysensors import BaseAsyncGateway

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    ATTR_DEVICES,
    DOMAIN,
    MYSENSORS_DISCOVERED_NODES,
    MYSENSORS_GATEWAYS,
    MYSENSORS_ON_UNLOAD,
    PLATFORMS,
    DevId,
    DiscoveryInfo,
    SensorType,
)
from .device import MySensorsChildEntity, get_mysensors_devices
from .gateway import finish_setup, gw_stop, setup_gateway

_LOGGER = logging.getLogger(__name__)

DATA_HASS_CONFIG = "hass_config"


CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an instance of the MySensors integration.

    Every instance has a connection to exactly one Gateway.
    """
    gateway = await setup_gateway(hass, entry)

    if not gateway:
        _LOGGER.error("Gateway setup failed for %s", entry.data)
        return False

    mysensors_data = hass.data.setdefault(DOMAIN, {})
    if MYSENSORS_GATEWAYS not in mysensors_data:
        mysensors_data[MYSENSORS_GATEWAYS] = {}
    mysensors_data[MYSENSORS_GATEWAYS][entry.entry_id] = gateway

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await finish_setup(hass, entry, gateway)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove an instance of the MySensors integration."""

    gateway: BaseAsyncGateway = hass.data[DOMAIN][MYSENSORS_GATEWAYS][entry.entry_id]

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    key = MYSENSORS_ON_UNLOAD.format(entry.entry_id)
    if key in hass.data[DOMAIN]:
        for fnct in hass.data[DOMAIN][key]:
            fnct()

        hass.data[DOMAIN].pop(key)

    del hass.data[DOMAIN][MYSENSORS_GATEWAYS][entry.entry_id]
    hass.data[DOMAIN].pop(MYSENSORS_DISCOVERED_NODES.format(entry.entry_id), None)

    await gw_stop(hass, entry, gateway)
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a MySensors config entry from a device."""
    gateway: BaseAsyncGateway = hass.data[DOMAIN][MYSENSORS_GATEWAYS][
        config_entry.entry_id
    ]
    device_id = next(
        device_id for domain, device_id in device_entry.identifiers if domain == DOMAIN
    )
    node_id = int(device_id.partition("-")[2])
    gateway.sensors.pop(node_id, None)
    gateway.tasks.persistence.need_save = True

    # remove node from discovered nodes
    hass.data[DOMAIN].setdefault(
        MYSENSORS_DISCOVERED_NODES.format(config_entry.entry_id), set()
    ).remove(node_id)

    return True


@callback
def setup_mysensors_platform(
    hass: HomeAssistant,
    domain: Platform,  # hass platform name
    discovery_info: DiscoveryInfo,
    device_class: type[MySensorsChildEntity]
    | Mapping[SensorType, type[MySensorsChildEntity]],
    device_args: (
        None | tuple
    ) = None,  # extra arguments that will be given to the entity constructor
    async_add_entities: Callable | None = None,
) -> list[MySensorsChildEntity] | None:
    """Set up a MySensors platform.

    Sets up a bunch of instances of a single platform that is supported by this
    integration.

    The function is given a list of device ids, each one describing an instance
    to set up. The function is also given a class.

    A new instance of the class is created for every device id, and the device
    id is given to the constructor of the class.
    """
    if device_args is None:
        device_args = ()
    new_devices: list[MySensorsChildEntity] = []
    new_dev_ids: list[DevId] = discovery_info[ATTR_DEVICES]
    for dev_id in new_dev_ids:
        devices: dict[DevId, MySensorsChildEntity] = get_mysensors_devices(hass, domain)
        if dev_id in devices:
            _LOGGER.debug(
                "Skipping setup of %s for platform %s as it already exists",
                dev_id,
                domain,
            )
            continue
        gateway_id, node_id, child_id, value_type = dev_id
        gateway: BaseAsyncGateway = hass.data[DOMAIN][MYSENSORS_GATEWAYS][gateway_id]

        if isinstance(device_class, dict):
            child = gateway.sensors[node_id].children[child_id]
            s_type = gateway.const.Presentation(child.type).name
            device_class_copy = device_class[s_type]
        else:
            device_class_copy = device_class

        args_copy = (*device_args, gateway_id, gateway, node_id, child_id, value_type)
        devices[dev_id] = device_class_copy(*args_copy)
        new_devices.append(devices[dev_id])
    if new_devices:
        _LOGGER.info("Adding new devices: %s", new_devices)
        if async_add_entities is not None:
            async_add_entities(new_devices)
    return new_devices
