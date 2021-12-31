"""Config flow to configure the GCE Eco-Devices integration."""
from pyecodevices import (
    EcoDevices,
    EcoDevicesCannotConnectError,
    EcoDevicesInvalidAuthError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import DEVICE_CLASSES as SENSOR_DEVICE_CLASSES
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_C1_DEVICE_CLASS,
    CONF_C1_ENABLED,
    CONF_C1_TOTAL_UNIT_OF_MEASUREMENT,
    CONF_C1_UNIT_OF_MEASUREMENT,
    CONF_C2_DEVICE_CLASS,
    CONF_C2_ENABLED,
    CONF_C2_TOTAL_UNIT_OF_MEASUREMENT,
    CONF_C2_UNIT_OF_MEASUREMENT,
    CONF_T1_ENABLED,
    CONF_T1_HCHP,
    CONF_T2_ENABLED,
    CONF_T2_HCHP,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=80): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        vol.Required(CONF_T1_ENABLED, default=False): bool,
        vol.Required(CONF_T2_ENABLED, default=False): bool,
        vol.Required(CONF_C1_ENABLED, default=False): bool,
        vol.Required(CONF_C2_ENABLED, default=False): bool,
    }
)


@config_entries.HANDLERS.register(DOMAIN)
class EcoDevicesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a eco-devices config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize class variables."""
        self.base_input = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=BASE_SCHEMA, errors=errors
            )

        entry = await self.async_set_unique_id(
            "_".join([DOMAIN, user_input[CONF_HOST], str(user_input[CONF_PORT])])
        )

        if entry:
            self._abort_if_unique_id_configured()

        session = async_get_clientsession(self.hass, False)

        errors = await _test_connection(session, user_input)

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=BASE_SCHEMA, errors=errors
            )

        self.base_input = user_input
        return await self.async_step_params()

    async def async_step_params(self, user_input=None):
        """Handle the param flow to customize the device accordly to enabled inputs."""
        if user_input is not None:
            user_input.update(self.base_input)
            return self.async_create_entry(
                title=f"Eco-Devices {user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="params",
            data_schema=vol.Schema(_get_params(self.base_input, {})),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return EcoDevicesOptionsFlowHandler(config_entry)


class EcoDevicesOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a EcoDevices options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry
        self.base_input = {}

    async def async_step_init(self, user_input):
        """Manage the options."""
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass, False)
            user_input[CONF_HOST] = self.config_entry.data[CONF_HOST]
            user_input[CONF_PORT] = self.config_entry.data[CONF_PORT]
            errors = await _test_connection(session, user_input)
            if not errors:
                self.base_input = user_input
                return await self.async_step_params()

        config = self.config_entry.data
        options = self.config_entry.options

        scan_interval = options.get(CONF_SCAN_INTERVAL, config.get(CONF_SCAN_INTERVAL))
        username = options.get(CONF_USERNAME, config.get(CONF_USERNAME))
        password = options.get(CONF_PASSWORD, config.get(CONF_PASSWORD))
        t1_enabled = options.get(CONF_T1_ENABLED, config.get(CONF_T1_ENABLED))
        t2_enabled = options.get(CONF_T2_ENABLED, config.get(CONF_T2_ENABLED))
        c1_enabled = options.get(CONF_C1_ENABLED, config.get(CONF_C1_ENABLED))
        c2_enabled = options.get(CONF_C2_ENABLED, config.get(CONF_C2_ENABLED))

        options_schema = {
            vol.Optional(CONF_USERNAME, default=username): str,
            vol.Optional(CONF_PASSWORD, default=password): str,
            vol.Required(CONF_SCAN_INTERVAL, default=scan_interval): int,
            vol.Required(CONF_T1_ENABLED, default=t1_enabled): bool,
            vol.Required(CONF_T2_ENABLED, default=t2_enabled): bool,
            vol.Required(CONF_C1_ENABLED, default=c1_enabled): bool,
            vol.Required(CONF_C2_ENABLED, default=c2_enabled): bool,
        }

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options_schema), errors=errors
        )

    async def async_step_params(self, user_input=None):
        """Handle the param flow to customize the device accordly to enabled inputs."""
        if user_input is not None:
            user_input.update(self.base_input)
            return self.async_create_entry(
                title=f"Eco-Devices {user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                data=user_input,
            )

        config = self.config_entry.data
        options = self.config_entry.options

        base_params = {
            CONF_T1_HCHP: options.get(
                CONF_T1_HCHP,
                config.get(CONF_T1_HCHP, False),
            ),
            CONF_T2_HCHP: options.get(
                CONF_T2_HCHP,
                config.get(CONF_T2_HCHP, False),
            ),
            CONF_C1_DEVICE_CLASS: options.get(
                CONF_C1_DEVICE_CLASS, config.get(CONF_C1_DEVICE_CLASS)
            ),
            CONF_C1_UNIT_OF_MEASUREMENT: options.get(
                CONF_C1_UNIT_OF_MEASUREMENT, config.get(CONF_C1_UNIT_OF_MEASUREMENT)
            ),
            CONF_C1_TOTAL_UNIT_OF_MEASUREMENT: options.get(
                CONF_C1_TOTAL_UNIT_OF_MEASUREMENT,
                config.get(CONF_C1_TOTAL_UNIT_OF_MEASUREMENT),
            ),
            CONF_C2_DEVICE_CLASS: options.get(
                CONF_C2_DEVICE_CLASS, config.get(CONF_C2_DEVICE_CLASS)
            ),
            CONF_C2_UNIT_OF_MEASUREMENT: options.get(
                CONF_C2_UNIT_OF_MEASUREMENT, config.get(CONF_C2_UNIT_OF_MEASUREMENT)
            ),
            CONF_C2_TOTAL_UNIT_OF_MEASUREMENT: options.get(
                CONF_C2_TOTAL_UNIT_OF_MEASUREMENT,
                config.get(CONF_C2_TOTAL_UNIT_OF_MEASUREMENT),
            ),
        }

        return self.async_show_form(
            step_id="params",
            data_schema=vol.Schema(_get_params(self.base_input, base_params)),
        )


async def _test_connection(session, user_input):
    errors = {}

    controller = EcoDevices(
        user_input[CONF_HOST],
        user_input[CONF_PORT],
        user_input.get(CONF_USERNAME),
        user_input.get(CONF_PASSWORD),
        session=session,
    )

    try:
        await controller.get_info()
    except EcoDevicesInvalidAuthError:
        errors["base"] = "invalid_auth"
    except EcoDevicesCannotConnectError:
        errors["base"] = "cannot_connect"

    return errors


def _get_params(base_input, base_params):
    params_schema = {}
    if base_input[CONF_T1_ENABLED]:
        params_schema.update(
            {
                vol.Required(
                    CONF_T1_HCHP,
                    default=base_params.get(CONF_T1_HCHP, False),
                ): bool,
            }
        )

    if base_input[CONF_T2_ENABLED]:
        params_schema.update(
            {
                vol.Required(
                    CONF_T2_HCHP,
                    default=base_params.get(CONF_T2_HCHP, False),
                ): bool,
            }
        )

    if base_input[CONF_C1_ENABLED]:
        params_schema.update(
            {
                vol.Required(
                    CONF_C1_DEVICE_CLASS, default=base_params.get(CONF_C1_DEVICE_CLASS)
                ): vol.All(str, vol.Lower, vol.In(SENSOR_DEVICE_CLASSES)),
                vol.Optional(
                    CONF_C1_UNIT_OF_MEASUREMENT,
                    default=base_params.get(CONF_C1_UNIT_OF_MEASUREMENT),
                ): str,
                vol.Optional(
                    CONF_C1_TOTAL_UNIT_OF_MEASUREMENT,
                    default=base_params.get(CONF_C1_TOTAL_UNIT_OF_MEASUREMENT),
                ): str,
            }
        )

    if base_input[CONF_C2_ENABLED]:
        params_schema.update(
            {
                vol.Required(
                    CONF_C2_DEVICE_CLASS, default=base_params.get(CONF_C2_DEVICE_CLASS)
                ): vol.All(str, vol.Lower, vol.In(SENSOR_DEVICE_CLASSES)),
                vol.Optional(
                    CONF_C2_UNIT_OF_MEASUREMENT,
                    default=base_params.get(CONF_C2_UNIT_OF_MEASUREMENT),
                ): str,
                vol.Optional(
                    CONF_C2_TOTAL_UNIT_OF_MEASUREMENT,
                    default=base_params.get(CONF_C2_TOTAL_UNIT_OF_MEASUREMENT),
                ): str,
            }
        )

    return params_schema
