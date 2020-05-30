"""
Config Flow for Wiser Rooms.

https://github.com/asantaga/wiserHomeAssistantPlatform
@msp1974

"""
import voluptuous as vol
from wiserHeatingAPI.wiserHub import (
    WiserHubAuthenticationException,
    WiserHubDataNull,
    WiserHubTimeoutException,
    WiserRESTException,
    wiserHub,
)

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistantError, callback

from .const import (
    _LOGGER,
    CONF_BOOST_TEMP,
    CONF_BOOST_TEMP_TIME,
    DEFAULT_BOOST_TEMP,
    DEFAULT_BOOST_TEMP_TIME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

data_schema = {
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_BOOST_TEMP, default=DEFAULT_BOOST_TEMP): int,
    vol.Optional(CONF_BOOST_TEMP_TIME, default=DEFAULT_BOOST_TEMP_TIME): int,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
}


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
        self.device_config = {}
        self.discovery_schema = None
        self._ip = None
        self._secret = None
        self._name = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return flow options."""
        return WiserOptionsFlowHandler(config_entry)

    async def _test_connection(self, ip, secret):
        """Allow test connection."""
        self.wiserhub = wiserHub(ip, secret)
        #        try:
        return await self.hass.async_add_executor_job(self.wiserhub.getWiserHubName)

    #        except:
    #            raise

    async def _create_entry(self):
        """
        Create entry for device.

        Generate a name to be used as a prefix for device entities.
        """
        self.device_config[CONF_NAME] = self._name
        title = self._name
        return self.async_create_entry(title=title, data=self.device_config)

    async def async_step_user(self, user_input=None):
        """
        Handle a Wiser Heat Hub config flow start.

        Manage device specific parameters.
        """
        errors = {}

        if user_input is not None:
            try:
                device = await self._test_connection(
                    ip=user_input[CONF_HOST], secret=user_input[CONF_PASSWORD]
                )

                self._name = device
                await self.async_set_unique_id(self._name)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_NAME: self._name,
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_BOOST_TEMP: user_input[CONF_BOOST_TEMP],
                        CONF_BOOST_TEMP_TIME: user_input[CONF_BOOST_TEMP_TIME],
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]
                        or DEFAULT_SCAN_INTERVAL,
                    }
                )

                # set device config values
                self.device_config = user_input
                return await self._create_entry()

            except WiserHubAuthenticationException:
                return self.async_abort(reason="auth_failure")
            except WiserHubTimeoutException:
                return self.async_abort(reason="timeout_error")
            except (WiserRESTException, WiserHubDataNull):
                return self.async_abort(reason="not_successful")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.discovery_schema or data_schema),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info):
        """Check that it is a Wiser Hub."""

        if not discovery_info.get("name") or not discovery_info["name"].startswith(
            "WiserHeat"
        ):
            return self.async_abort(reason="not_wiser_device")

        self._host = discovery_info[CONF_HOST].rstrip(".")
        self._type = discovery_info["type"]
        self._name = discovery_info["name"].replace("." + self._type, "")
        self._title = self._name
        self._manufacturer = "Wiser"

        await self.async_set_unique_id(self._name)

        # If already configured then abort config
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host, CONF_NAME: self._name}
        )

        # replace placeholder with hub mDNS name
        self.context["title_placeholders"] = {
            CONF_NAME: self._name,
        }

        self.discovery_schema = {
            vol.Required(CONF_HOST, default=self._host): str,
            vol.Required(CONF_PASSWORD,): str,
            vol.Optional(CONF_BOOST_TEMP, default=DEFAULT_BOOST_TEMP): int,
            vol.Optional(CONF_BOOST_TEMP_TIME, default=DEFAULT_BOOST_TEMP_TIME): int,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        }

        return await self.async_step_user()

    async def async_step_import(self, import_data):
        """
        Import wiser config from configuration.yaml.

        Triggered by async_setup only if a config entry doesn't already exist.
        We will attempt to validate the credentials
        and create an entry if valid. Otherwise, we will delegate to the user
        step so that the user can continue the config flow.
        """
        user_input = {}
        try:
            user_input = {
                CONF_HOST: import_data[0][CONF_HOST],
                CONF_PASSWORD: import_data[0][CONF_PASSWORD],
                CONF_BOOST_TEMP: import_data[0].get(
                    CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP
                ),
                CONF_BOOST_TEMP_TIME: import_data[0].get(
                    CONF_BOOST_TEMP_TIME, DEFAULT_BOOST_TEMP_TIME
                ),
                CONF_SCAN_INTERVAL: import_data[0].get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            }
        except (HomeAssistantError, KeyError):
            _LOGGER.debug(
                "No valid wiser configuration found for import, delegating to user step"
            )
            return await self.async_step_user(user_input=user_input)

        # Removing exception handler for now
        #       try:
        device = await self._test_connection(
            ip=user_input.get(CONF_HOST), secret=user_input.get(CONF_PASSWORD),
        )

        self._name = device
        await self.async_set_unique_id(self._name)

        self._abort_if_unique_id_configured(
            updates={
                CONF_NAME: self._name,
                CONF_HOST: user_input[CONF_HOST],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_BOOST_TEMP: user_input[CONF_BOOST_TEMP],
                CONF_BOOST_TEMP_TIME: user_input[CONF_BOOST_TEMP_TIME],
                CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]
                or DEFAULT_SCAN_INTERVAL,
            }
        )

        # set device config values
        self.device_config = user_input

        return await self._create_entry()


#        except:
#            _LOGGER.debug(
#                "Error connecting to Wiser Hub using configuration found for import, delegating to user step"
#            )
#            return await self.async_step_user(user_input=user_input)


class WiserOptionsFlowHandler(config_entries.OptionsFlow):
    """Main Class for Wiser Options in ConfigFlow."""

    def __init__(self, config_entry):
        """Initialize deCONZ options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.data)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Manage the wiser devices options."""
        if user_input is not None:
            self.options[CONF_BOOST_TEMP] = user_input[CONF_BOOST_TEMP]
            self.options[CONF_BOOST_TEMP_TIME] = user_input[CONF_BOOST_TEMP_TIME]
            self.options[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]

            # Update main data config instead of option config
            self.hass.config_entries.async_update_entry(
                entry=self.config_entry, data=self.options,
            )

            # Have to create an options config to work but not used.
            return self.async_create_entry(
                title=self.config_entry.title, data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BOOST_TEMP,
                        default=self.options.get(CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP),
                    ): int,
                    vol.Required(
                        CONF_BOOST_TEMP_TIME,
                        default=self.options.get(
                            CONF_BOOST_TEMP_TIME, DEFAULT_BOOST_TEMP_TIME
                        ),
                    ): int,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): int,
                }
            ),
        )
