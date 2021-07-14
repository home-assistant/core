"""Config flow for DroneMobile integration."""
import logging

from drone_mobile import Vehicle
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import (
    CONF_UNIT,
    CONF_UNITS,
    CONF_UPDATE_INTERVAL,
    CONF_VEHICLE_ID,
    DEFAULT_UNIT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_UNIT, default=DEFAULT_UNIT): vol.In(CONF_UNITS),
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=2, max=60)),
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DroneMobile."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Create a new instance of the flow handler."""
        self.username = None
        self.password = None
        self.unit = None
        self.update_interval = None
        self.vehicle_id = None
        self.vehicles_options = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)

    async def async_step_import(self, user_input=None):
        """Occurs when a previously setup entry fails and is re-initiated."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle the initial configuration."""
        errors = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
                self.username = user_input[CONF_USERNAME]
                self.password = user_input[CONF_PASSWORD]
                self.unit = user_input[CONF_UNIT]
                self.update_interval = user_input[CONF_UPDATE_INTERVAL]
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=DATA_SCHEMA,
                    errors=errors,
                )
            else:
                # Show the next screen
                return await self.async_step_select_vehicle(user_input)
        else:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors=errors,
            )

    async def async_step_select_vehicle(self, user_input=None):
        """Ask user to select the vehicle to setup."""
        errors = {}
        if user_input is None or CONF_VEHICLE_ID not in user_input:
            # Get available vehicles
            existing_vehicles = [
                entry.data[CONF_VEHICLE_ID] for entry in self._async_current_entries()
            ]
            vehicles = await get_vehicles(self.hass, user_input)
            vehicles_options = {
                vehicle["id"]: vehicle["vehicle_name"]
                for vehicle in vehicles
                if vehicle["id"] not in existing_vehicles
            }
            if not vehicles_options:
                return self.async_abort(reason="no_available_vehicles")
            else:
                self.vehicles_options = vehicles_options

            return self.async_show_form(
                step_id="select_vehicle",
                data_schema=vol.Schema(
                    {vol.Required(CONF_VEHICLE_ID): vol.In(vehicles_options)}
                ),
                errors=errors,
            )

        self.vehicle_id = user_input[CONF_VEHICLE_ID]

        # Show the next screen
        return await self.async_step_install()

    async def async_step_install(self, data=None):
        """Create a config entry at completion of the flow."""
        data = {
            CONF_USERNAME: self.username,
            CONF_PASSWORD: self.password,
            CONF_UNIT: self.unit,
            CONF_UPDATE_INTERVAL: self.update_interval,
            CONF_VEHICLE_ID: self.vehicle_id,
        }

        await self.async_set_unique_id("drone_mobile_vehicle_" + str(self.vehicle_id))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=self.vehicles_options[self.vehicle_id], data=data)

class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        options = {
            vol.Optional(
                CONF_UNIT,
                default=self.config_entry.options.get(CONF_UNIT, DEFAULT_UNIT),
            ): vol.In(CONF_UNITS),
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=2, max=60)),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                options
            )
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    vehicle = Vehicle(data[CONF_USERNAME], data[CONF_PASSWORD])

    try:
        result = await hass.async_add_executor_job(
            vehicle.auth
        )

    except Exception as ex:
        _LOGGER.error(ex)
        raise InvalidAuth from ex

    if not result:
        _LOGGER.error("Failed to authenticate with DroneMobile")
        raise CannotConnect
    return True

async def get_vehicles(hass: core.HomeAssistant, data):
    vehicleObject = Vehicle(data[CONF_USERNAME], data[CONF_PASSWORD])
    try:
        vehicles = await hass.async_add_executor_job(
            vehicleObject.getAllVehicles
        )
        return vehicles
    except Exception as ex:
        _LOGGER.error(ex)
        raise InvalidAuth from ex

    if not vehicles:
        _LOGGER.error("Error communicating with DroneMobile for %s", vehicleObject.username)
        raise CannotConnect