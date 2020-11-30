"""Support for LCN devices."""
import asyncio
import logging

import pypck

from homeassistant import config_entries
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity

from .const import CONF_DIM_MODE, CONF_SK_NUM_TRIES, DOMAIN
from .schemas import CONFIG_SCHEMA  # noqa: F401
from .services import (
    DynText,
    Led,
    LockKeys,
    LockRegulator,
    OutputAbs,
    OutputRel,
    OutputToggle,
    Pck,
    Relays,
    SendKeys,
    VarAbs,
    VarRel,
    VarReset,
)

PLATFORMS = ["binary_sensor", "climate", "cover", "light", "scene", "sensor", "switch"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry):
    """Set up a connection to PCHK host from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    settings = {
        "SK_NUM_TRIES": config_entry.data[CONF_SK_NUM_TRIES],
        "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[config_entry.data[CONF_DIM_MODE]],
    }

    # connect to PCHK
    if config_entry.entry_id not in hass.data[DOMAIN]:
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
            _LOGGER.info('LCN connected to "%s"', config_entry.title)
            hass.data[DOMAIN][config_entry.entry_id] = {
                CONNECTION: lcn_connection,
            }
        except pypck.connection.PchkAuthenticationError:
            _LOGGER.warning('Authentication on PCHK "%s" failed.', config_entry.title)
            return False
        except pypck.connection.PchkLicenseError:
            _LOGGER.warning(
                'Maximum number of connections on PCHK "%s" was '
                "reached. An additional license key is required.",
                config_entry.title,
            )
            return False
        except TimeoutError:
            _LOGGER.warning('Connection to PCHK "%s" failed.', config_entry.title)
            return False

        # remove orphans from entity registry which are in ConfigEntry but were removed
        # from configuration.yaml
        if config_entry.source == config_entries.SOURCE_IMPORT:
            entity_registry = await er.async_get_registry(hass)
            entity_registry.async_clear_config_entry(config_entry.entry_id)

        # forward config_entry to components
        for component in PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, component)
            )

    return True


async def async_unload_entry(hass, config_entry):
    """Close connection to PCHK host represented by config_entry."""
    # forward unloading to platforms
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok and config_entry.entry_id in hass.data[DOMAIN]:
        host = hass.data[DOMAIN].pop(config_entry.entry_id)
        await host[CONNECTION].async_close()

    return unload_ok


async def async_setup(hass, config):
    """Set up the LCN component."""
    if DOMAIN not in config:
        return True

    # register service calls
    for service_name, service in (
        ("output_abs", OutputAbs),
        ("output_rel", OutputRel),
        ("output_toggle", OutputToggle),
        ("relays", Relays),
        ("var_abs", VarAbs),
        ("var_reset", VarReset),
        ("var_rel", VarRel),
        ("lock_regulator", LockRegulator),
        ("led", Led),
        ("send_keys", SendKeys),
        ("lock_keys", LockKeys),
        ("dyn_text", DynText),
        ("pck", Pck),
    ):
        hass.services.async_register(
            DOMAIN, service_name, service(hass).async_call_service, service.schema
        )

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


class LcnEntity(Entity):
    """Parent class for all entities associated with the LCN component."""

    def __init__(self, config, host_id, device_connection):
        """Initialize the LCN device."""
        self.config = config
        self.host_id = host_id
        self.device_connection = device_connection
        self.unregister_for_inputs = None
        self._name = config[CONF_NAME]

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.host_id}-{self.config[CONF_UNIQUE_ID]}"

    @property
    def should_poll(self):
        """Lcn device entity pushes its state to HA."""
        return False

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        if not self.device_connection.is_group:
            self.unregister_for_inputs = self.device_connection.register_for_inputs(
                self.input_received
            )

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        if self.unregister_for_inputs is not None:
            self.unregister_for_inputs()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    def input_received(self, input_obj):
        """Set state/value when LCN input object (command) is received."""
