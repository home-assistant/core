"""Support for LCN devices."""
import logging

import pypck

from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_COVERS,
    CONF_HOST,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_USERNAME,
)
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_CLIMATES,
    CONF_CONNECTIONS,
    CONF_DIM_MODE,
    CONF_SCENES,
    CONF_SK_NUM_TRIES,
    DATA_LCN,
    DOMAIN,
)
from .schemas import CONFIG_SCHEMA  # noqa: 401
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

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the LCN component."""
    hass.data[DATA_LCN] = {}

    conf_connections = config[DOMAIN][CONF_CONNECTIONS]
    connections = []
    for conf_connection in conf_connections:
        connection_name = conf_connection.get(CONF_NAME)

        settings = {
            "SK_NUM_TRIES": conf_connection[CONF_SK_NUM_TRIES],
            "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[
                conf_connection[CONF_DIM_MODE]
            ],
        }

        connection = pypck.connection.PchkConnectionManager(
            conf_connection[CONF_HOST],
            conf_connection[CONF_PORT],
            conf_connection[CONF_USERNAME],
            conf_connection[CONF_PASSWORD],
            settings=settings,
            connection_id=connection_name,
        )

        try:
            # establish connection to PCHK server
            await hass.async_create_task(connection.async_connect(timeout=15))
            connections.append(connection)
            _LOGGER.info('LCN connected to "%s"', connection_name)
        except TimeoutError:
            _LOGGER.error('Connection to PCHK server "%s" failed', connection_name)
            return False

    hass.data[DATA_LCN][CONF_CONNECTIONS] = connections

    # load platforms
    for component, conf_key in (
        ("binary_sensor", CONF_BINARY_SENSORS),
        ("climate", CONF_CLIMATES),
        ("cover", CONF_COVERS),
        ("light", CONF_LIGHTS),
        ("scene", CONF_SCENES),
        ("sensor", CONF_SENSORS),
        ("switch", CONF_SWITCHES),
    ):
        if conf_key in config[DOMAIN]:
            hass.async_create_task(
                async_load_platform(
                    hass, component, DOMAIN, config[DOMAIN][conf_key], config
                )
            )

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

    return True


class LcnEntity(Entity):
    """Parent class for all devices associated with the LCN component."""

    def __init__(self, config, device_connection):
        """Initialize the LCN device."""
        self.config = config
        self.device_connection = device_connection
        self._name = config[CONF_NAME]

    @property
    def should_poll(self):
        """Lcn device entity pushes its state to HA."""
        return False

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        self.device_connection.register_for_inputs(self.input_received)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    def input_received(self, input_obj):
        """Set state/value when LCN input object (command) is received."""
