"""
Config Flow for Wiser Rooms.

https://github.com/asantaga/wiserHomeAssistantPlatform
@msp1974

"""
import requests.exceptions
import voluptuous as vol
from wiserHeatingAPI.wiserHub import (
    WiserHubAuthenticationException,
    WiserHubDataNull,
    WiserHubTimeoutException,
    WiserRESTException,
    wiserHub,
)

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import callback

from .const import (
    _LOGGER,
    CONF_BOOST_TEMP,
    CONF_BOOST_TEMP_TIME,
    DEFAULT_BOOST_TEMP,
    DEFAULT_BOOST_TEMP_TIME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_BOOST_TEMP, default=DEFAULT_BOOST_TEMP): int,
        vol.Optional(CONF_BOOST_TEMP_TIME, default=DEFAULT_BOOST_TEMP_TIME): int,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


async def validate_input(hass, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    try:
        wiser = await hass.async_add_executor_job(
            wiserHub, data[CONF_HOST], data[CONF_PASSWORD]
        )
        wiserID = await hass.async_add_executor_job(wiser.getWiserHubName)
    except AttributeError:
        # bug in wiser api needs fixing
        raise WiserHubDataNull
    except requests.exceptions.ConnectionError:
        raise WiserHubTimeoutException
    except Exception:
        raise

    unique_id = str(f"{DOMAIN}-{wiserID}")
    name = wiserID

    return {"title": name, "unique_id": unique_id}


@config_entries.HANDLERS.register(DOMAIN)
class WiserFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """
    WiserFlowHandler configuration method.

    The schema version of the entries that it creates
    Home Assistant will call your migrate method if the version changes
    (this is not implemented yet)
    """

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the wiser flow."""
        self.discovery_schema = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return flow options."""
        return WiserOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """
        Handle a Wiser Heat Hub config flow start.

        Manage device specific parameters.
        """
        errors = {}
        if user_input is not None:
            try:
                validated = await validate_input(self.hass, user_input)
            except WiserHubAuthenticationException:
                errors["base"] = "auth_failure"
            except WiserHubTimeoutException:
                errors["base"] = "timeout_error"
            except (WiserRESTException, WiserHubDataNull):
                errors["base"] = "not_successful"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(validated["unique_id"])
                self._abort_if_unique_id_configured()

                # Add hub name to config
                user_input[CONF_NAME] = validated["title"]
                return self.async_create_entry(
                    title=validated["title"], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.discovery_schema or DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info):
        """Check that it is a Wiser Hub."""
        if not discovery_info.get("name") or not discovery_info["name"].startswith(
            "WiserHeat"
        ):
            return self.async_abort(reason="not_wiser_device")

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        properties = {
            CONF_HOST: discovery_info[CONF_HOST].rstrip("."),
            CONF_NAME: discovery_info["name"].replace("." + discovery_info["type"], ""),
        }

        await self.async_set_unique_id("{}-{}".format(DOMAIN, properties[CONF_NAME]))

        # replace placeholder with hub mDNS name
        self.context["title_placeholders"] = {
            CONF_NAME: properties[CONF_NAME],
        }

        # If discovered via zero conf, set host
        self.discovery_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=properties[CONF_HOST]): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_BOOST_TEMP, default=DEFAULT_BOOST_TEMP): int,
                vol.Optional(
                    CONF_BOOST_TEMP_TIME, default=DEFAULT_BOOST_TEMP_TIME
                ): int,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
            }
        )

        return await self.async_step_user()

    async def async_step_import(self, import_data):
        """
        Import wiser config from configuration.yaml.

        Triggered by async_setup only if a config entry doesn't already exist.
        We will attempt to validate the credentials
        and create an entry if valid. Otherwise, we will delegate to the user
        step so that the user can continue the config flow.
        """
        if self._host_already_configured(import_data):
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(import_data)

    def _host_already_configured(self, user_input):
        """See if we already have a username matching user input configured."""
        existing_host = {
            entry.data[CONF_HOST] for entry in self._async_current_entries()
        }
        return user_input[CONF_HOST] in existing_host


class WiserOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for wiser hub."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_BOOST_TEMP,
                    default=self.config_entry.options.get(
                        CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP
                    ),
                ): int,
                vol.Optional(
                    CONF_BOOST_TEMP_TIME,
                    default=self.config_entry.options.get(
                        CONF_BOOST_TEMP_TIME, DEFAULT_BOOST_TEMP_TIME
                    ),
                ): int,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
