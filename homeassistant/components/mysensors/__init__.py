"""Connect to a MySensors gateway via pymysensors API."""
from __future__ import annotations

from collections.abc import Callable
from functools import partial
import logging

from mysensors import BaseAsyncGateway

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DEVICES,
    DOMAIN,
    MYSENSORS_DISCOVERY,
    MYSENSORS_GATEWAYS,
    MYSENSORS_ON_UNLOAD,
    PLATFORMS_WITH_ENTRY_SUPPORT,
    DevId,
    DiscoveryInfo,
    SensorType,
)
from .device import MySensorsDevice, get_mysensors_devices
from .gateway import finish_setup, gw_stop, setup_gateway
from .helpers import on_unload

_LOGGER = logging.getLogger(__name__)

DATA_HASS_CONFIG = "hass_config"


CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the MySensors component."""
    # This is needed to set up the notify platform via discovery.
    hass.data[DOMAIN] = {DATA_HASS_CONFIG: config}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an instance of the MySensors integration.

    Every instance has a connection to exactly one Gateway.
    """
    gateway = await setup_gateway(hass, entry)

    if not gateway:
        _LOGGER.error("Gateway setup failed for %s", entry.data)
        return False

    if MYSENSORS_GATEWAYS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][MYSENSORS_GATEWAYS] = {}
    hass.data[DOMAIN][MYSENSORS_GATEWAYS][entry.entry_id] = gateway

    # Connect notify discovery as that integration doesn't support entry forwarding.
    # Allow loading device tracker platform via discovery
    # until refactor to config entry is done.

    for platform in (Platform.DEVICE_TRACKER, Platform.NOTIFY):
        load_discovery_platform = partial(
            async_load_platform,
            hass,
            platform,
            DOMAIN,
            hass_config=hass.data[DOMAIN][DATA_HASS_CONFIG],
        )

        on_unload(
            hass,
            entry.entry_id,
            async_dispatcher_connect(
                hass,
                MYSENSORS_DISCOVERY.format(entry.entry_id, platform),
                load_discovery_platform,
            ),
        )

    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS_WITH_ENTRY_SUPPORT
    )
    await finish_setup(hass, entry, gateway)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove an instance of the MySensors integration."""

    gateway: BaseAsyncGateway = hass.data[DOMAIN][MYSENSORS_GATEWAYS][entry.entry_id]

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_WITH_ENTRY_SUPPORT
    )
    if not unload_ok:
        return False

    key = MYSENSORS_ON_UNLOAD.format(entry.entry_id)
    if key in hass.data[DOMAIN]:
        for fnct in hass.data[DOMAIN][key]:
            fnct()

        hass.data[DOMAIN].pop(key)

    del hass.data[DOMAIN][MYSENSORS_GATEWAYS][entry.entry_id]

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

    return True


@callback
def setup_mysensors_platform(
    hass: HomeAssistant,
    domain: Platform,  # hass platform name
    discovery_info: DiscoveryInfo,
    device_class: type[MySensorsDevice] | dict[SensorType, type[MySensorsDevice]],
    device_args: (
        None | tuple
    ) = None,  # extra arguments that will be given to the entity constructor
    async_add_entities: Callable | None = None,
) -> list[MySensorsDevice] | None:
    """Set up a MySensors platform.

    Sets up a bunch of instances of a single platform that is supported by this integration.
    The function is given a list of device ids, each one describing an instance to set up.
    The function is also given a class.
    A new instance of the class is created for every device id, and the device id is given to the constructor of the class
    """
    if device_args is None:
        device_args = ()
    new_devices: list[MySensorsDevice] = []
    new_dev_ids: list[DevId] = discovery_info[ATTR_DEVICES]
    for dev_id in new_dev_ids:
        devices: dict[DevId, MySensorsDevice] = get_mysensors_devices(hass, domain)
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
            async_add_entities(new_devices, True)
    return new_devices
