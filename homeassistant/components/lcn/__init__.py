"""Support for LCN devices."""
from __future__ import annotations

from collections.abc import Callable
from functools import partial
import logging

import pypck

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DIM_MODE,
    CONF_DOMAIN_DATA,
    CONF_SK_NUM_TRIES,
    CONNECTION,
    DOMAIN,
    PLATFORMS,
)
from .helpers import (
    AddressType,
    DeviceConnectionType,
    InputType,
    async_update_config_entry,
    generate_unique_id,
    get_device_model,
    import_lcn_config,
    register_lcn_address_devices,
    register_lcn_host_device,
)
from .schemas import CONFIG_SCHEMA  # noqa: F401
from .services import SERVICES

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LCN component."""
    if DOMAIN not in config:
        return True

    # initialize a config_flow for all LCN configurations read from
    # configuration.yaml
    config_entries_data = import_lcn_config(config[DOMAIN])

    for config_entry_data in config_entries_data:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=config_entry_data,
            )
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Set up a connection to PCHK host from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    if config_entry.entry_id in hass.data[DOMAIN]:
        return False

    settings = {
        "SK_NUM_TRIES": config_entry.data[CONF_SK_NUM_TRIES],
        "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[config_entry.data[CONF_DIM_MODE]],
    }

    # connect to PCHK
    lcn_connection = pypck.connection.PchkConnectionManager(
        config_entry.data[CONF_IP_ADDRESS],
        config_entry.data[CONF_PORT],
        config_entry.data[CONF_USERNAME],
        config_entry.data[CONF_PASSWORD],
        settings=settings,
        connection_id=config_entry.entry_id,
    )
    try:
        # establish connection to PCHK server
        await lcn_connection.async_connect(timeout=15)
    except pypck.connection.PchkAuthenticationError:
        _LOGGER.warning('Authentication on PCHK "%s" failed', config_entry.title)
        return False
    except pypck.connection.PchkLicenseError:
        _LOGGER.warning(
            'Maximum number of connections on PCHK "%s" was '
            "reached. An additional license key is required",
            config_entry.title,
        )
        return False
    except TimeoutError:
        _LOGGER.warning('Connection to PCHK "%s" failed', config_entry.title)
        return False

    _LOGGER.debug('LCN connected to "%s"', config_entry.title)
    hass.data[DOMAIN][config_entry.entry_id] = {
        CONNECTION: lcn_connection,
    }
    # Update config_entry with LCN device serials
    await async_update_config_entry(hass, config_entry)

    # register/update devices for host, modules and groups in device registry
    register_lcn_host_device(hass, config_entry)
    register_lcn_address_devices(hass, config_entry)

    # forward config_entry to components
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    # register for LCN bus messages
    device_registry = dr.async_get(hass)
    input_received = partial(
        async_host_input_received, hass, config_entry, device_registry
    )
    lcn_connection.register_for_inputs(input_received)

    # register service calls
    for service_name, service in SERVICES:
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(
                DOMAIN, service_name, service(hass).async_call_service, service.schema
            )

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Close connection to PCHK host represented by config_entry."""
    # forward unloading to platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok and config_entry.entry_id in hass.data[DOMAIN]:
        host = hass.data[DOMAIN].pop(config_entry.entry_id)
        await host[CONNECTION].async_close()

    # unregister service calls
    if unload_ok and not hass.data[DOMAIN]:  # check if this is the last entry to unload
        for service_name, _ in SERVICES:
            hass.services.async_remove(DOMAIN, service_name)

    return unload_ok


def async_host_input_received(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    device_registry: dr.DeviceRegistry,
    inp: pypck.inputs.Input,
) -> None:
    """Process received input object (command) from LCN bus."""
    if not isinstance(inp, pypck.inputs.ModInput):
        return

    lcn_connection = hass.data[DOMAIN][config_entry.entry_id][CONNECTION]
    logical_address = lcn_connection.physical_to_logical(inp.physical_source_addr)
    address = (
        logical_address.seg_id,
        logical_address.addr_id,
        logical_address.is_group,
    )
    identifiers = {(DOMAIN, generate_unique_id(config_entry.entry_id, address))}
    device = device_registry.async_get_device(identifiers, set())
    if device is None:
        return

    if isinstance(inp, pypck.inputs.ModStatusAccessControl):
        _async_fire_access_control_event(hass, device, address, inp)
    elif isinstance(inp, pypck.inputs.ModSendKeysHost):
        _async_fire_send_keys_event(hass, device, address, inp)


def _async_fire_access_control_event(
    hass: HomeAssistant, device: dr.DeviceEntry, address: AddressType, inp: InputType
) -> None:
    """Fire access control event (transponder, transmitter, fingerprint, codelock)."""
    event_data = {
        "segment_id": address[0],
        "module_id": address[1],
        "code": inp.code,
    }

    if device is not None:
        event_data.update({CONF_DEVICE_ID: device.id})

    if inp.periphery == pypck.lcn_defs.AccessControlPeriphery.TRANSMITTER:
        event_data.update(
            {"level": inp.level, "key": inp.key, "action": inp.action.value}
        )

    event_name = f"lcn_{inp.periphery.value.lower()}"
    hass.bus.async_fire(event_name, event_data)


def _async_fire_send_keys_event(
    hass: HomeAssistant, device: dr.DeviceEntry, address: AddressType, inp: InputType
) -> None:
    """Fire send_keys event."""
    for table, action in enumerate(inp.actions):
        if action == pypck.lcn_defs.SendKeyCommand.DONTSEND:
            continue

        for key, selected in enumerate(inp.keys):
            if not selected:
                continue
            event_data = {
                "segment_id": address[0],
                "module_id": address[1],
                "key": pypck.lcn_defs.Key(table * 8 + key).name.lower(),
                "action": action.name.lower(),
            }

            if device is not None:
                event_data.update({CONF_DEVICE_ID: device.id})

            hass.bus.async_fire("lcn_send_keys", event_data)


class LcnEntity(Entity):
    """Parent class for all entities associated with the LCN component."""

    def __init__(
        self, config: ConfigType, entry_id: str, device_connection: DeviceConnectionType
    ) -> None:
        """Initialize the LCN device."""
        self.config = config
        self.entry_id = entry_id
        self.device_connection = device_connection
        self._unregister_for_inputs: Callable | None = None
        self._name: str = config[CONF_NAME]

    @property
    def address(self) -> AddressType:
        """Return LCN address."""
        return (
            self.device_connection.seg_id,
            self.device_connection.addr_id,
            self.device_connection.is_group,
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return generate_unique_id(
            self.entry_id, self.address, self.config[CONF_RESOURCE]
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        address = f"{'g' if self.address[2] else 'm'}{self.address[0]:03d}{self.address[1]:03d}"
        model = f"LCN resource ({get_device_model(self.config[CONF_DOMAIN], self.config[CONF_DOMAIN_DATA])})"

        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": f"{address}.{self.config[CONF_RESOURCE]}",
            "model": model,
            "manufacturer": "Issendorff",
            "via_device": (
                DOMAIN,
                generate_unique_id(self.entry_id, self.config[CONF_ADDRESS]),
            ),
        }

    @property
    def should_poll(self) -> bool:
        """Lcn device entity pushes its state to HA."""
        return False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        if not self.device_connection.is_group:
            self._unregister_for_inputs = self.device_connection.register_for_inputs(
                self.input_received
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._unregister_for_inputs is not None:
            self._unregister_for_inputs()

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    def input_received(self, input_obj: InputType) -> None:
        """Set state/value when LCN input object (command) is received."""
