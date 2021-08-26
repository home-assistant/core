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
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_C1_DEVICE_CLASS,
    CONF_C1_ENABLED,
    CONF_C1_UNIT_OF_MEASUREMENT,
    CONF_C2_DEVICE_CLASS,
    CONF_C2_ENABLED,
    CONF_C2_UNIT_OF_MEASUREMENT,
    CONF_T1_ENABLED,
    CONF_T1_UNIT_OF_MEASUREMENT,
    CONF_T2_ENABLED,
    CONF_T2_UNIT_OF_MEASUREMENT,
    DEFAULT_T1_UNIT_OF_MEASUREMENT,
    DEFAULT_T2_UNIT_OF_MEASUREMENT,
    DOMAIN,
)

BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=80): int,
        vol.Required(CONF_SCAN_INTERVAL, default=5): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
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

        entry = await self.async_set_unique_id(f"{DOMAIN}, {user_input.get(CONF_HOST)}")

        if entry:
            self._abort_if_unique_id_configured()

        session = async_get_clientsession(self.hass, False)

        controller = EcoDevices(
            user_input.get(CONF_HOST),
            user_input.get(CONF_PORT),
            user_input.get(CONF_USERNAME),
            user_input.get(CONF_PASSWORD),
            session=session,
        )

        try:
            await controller.get_info()
        except EcoDevicesInvalidAuthError:
            errors["base"] = "invalid_auth"
            return self.async_show_form(
                step_id="user", data_schema=BASE_SCHEMA, errors=errors
            )
        except EcoDevicesCannotConnectError:
            errors["base"] = "cannot_connect"
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
                title=user_input.get(CONF_HOST), data=user_input
            )

        params_schema = {}
        if self.base_input.get(CONF_T1_ENABLED):
            params_schema.update(
                {
                    vol.Required(
                        CONF_T1_UNIT_OF_MEASUREMENT,
                        default=DEFAULT_T1_UNIT_OF_MEASUREMENT,
                    ): str,
                }
            )

        if self.base_input.get(CONF_T2_ENABLED):
            params_schema.update(
                {
                    vol.Required(
                        CONF_T2_UNIT_OF_MEASUREMENT,
                        default=DEFAULT_T2_UNIT_OF_MEASUREMENT,
                    ): str,
                }
            )

        if self.base_input.get(CONF_C1_ENABLED):
            params_schema.update(
                {
                    vol.Required(CONF_C1_DEVICE_CLASS): vol.All(
                        str, vol.Lower, vol.In(SENSOR_DEVICE_CLASSES)
                    ),
                    vol.Optional(CONF_C1_UNIT_OF_MEASUREMENT): str,
                }
            )

        if self.base_input.get(CONF_C2_ENABLED):
            params_schema.update(
                {
                    vol.Required(CONF_C2_DEVICE_CLASS): vol.All(
                        str, vol.Lower, vol.In(SENSOR_DEVICE_CLASSES)
                    ),
                    vol.Optional(CONF_C2_UNIT_OF_MEASUREMENT): str,
                }
            )

        return self.async_show_form(
            step_id="params", data_schema=vol.Schema(params_schema)
        )
