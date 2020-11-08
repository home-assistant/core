"""Config flow for Bosch Smart Home Controller integration."""
import logging

from boschshcpy import SHCInformation, SHCSession
import voluptuous as vol
from zeroconf import Error as ZeroconfError, ServiceStateChange

from homeassistant import config_entries, core, exceptions
from homeassistant.components.zeroconf import (
    HaServiceBrowser,
    async_get_instance,
    info_from_service,
)
from homeassistant.const import CONF_HOST

from .const import CONF_SSL_CERTIFICATE, CONF_SSL_KEY
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_SSL_CERTIFICATE): str,
        vol.Required(CONF_SSL_KEY): str,
    }
)


class SHCListener:
    """SHC Listener for Zeroconf browser updates."""

    def __init__(self) -> None:
        """Initialize SHC Listener."""
        self.shc_services = {}

    def service_update(self, zeroconf, service_type, name, state_change):
        """Service state changed."""

        if state_change != ServiceStateChange.Added:
            return

        try:
            service_info = zeroconf.get_service_info(service_type, name)
        except ZeroconfError:
            _LOGGER.exception("Failed to get info for device %s", name)
            return
        if not service_info:
            # Prevent the browser thread from collapsing as
            # service_info can be None
            _LOGGER.debug("Failed to get info for device %s", name)
            return

        self.shc_services[name] = service_info

        info = info_from_service(service_info)
        if not info:
            # Prevent the browser thread from collapsing
            _LOGGER.debug("Failed to get addresses for device %s", name)
            return

        _LOGGER.debug("Discovered new device %s %s", name, info)
        return


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session: SHCSession
    session = await hass.async_add_executor_job(
        SHCSession,
        data[CONF_HOST],
        data[CONF_SSL_CERTIFICATE],
        data[CONF_SSL_KEY],
        True,
    )

    zeroconf = await async_get_instance(hass)

    listener = SHCListener()
    HaServiceBrowser(zeroconf, "_http._tcp.local.", handlers=[listener.service_update])
    zc_service_info = listener.shc_services

    session.set_zeroconf_info(zc_service_info)
    # if session.name is None or session.mac_address is None:
    #     raise InvalidAuth

    session_information: SHCInformation
    await hass.async_add_executor_job(session.authenticate)
    session_information = session.information
    if session_information is None:
        raise InvalidAuth

    return {"title": "Bosch SHC", "name": session.name, "mac": session.mac_address}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch SHC."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    info = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                # Check if already configured
                await self.async_set_unique_id(info["mac"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_SSL_CERTIFICATE: user_input[CONF_SSL_CERTIFICATE],
                        CONF_SSL_KEY: user_input[CONF_SSL_KEY],
                    },
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_credentials(self, user_input=None):
        """Handle the credentials step."""
        errors = {}
        if user_input is not None:
            try:
                device_info = await validate_input(self.hass, user_input)
            # except aiohttp.ClientResponseError as error:
            #     if error.status == HTTP_UNAUTHORIZED:
            #         errors["base"] = "invalid_auth"
            #     else:
            #         errors["base"] = "cannot_connect"
            # except HTTP_CONNECT_ERRORS:
            #     errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=device_info["title"] or device_info["hostname"],
                    data={**user_input, CONF_HOST: self.host},
                )
        else:
            user_input = {}

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SSL_CERTIFICATE, default=user_input.get(CONF_SSL_CERTIFICATE)
                ): str,
                vol.Required(CONF_SSL_KEY, default=user_input.get(CONF_SSL_KEY)): str,
            }
        )

        return self.async_show_form(
            step_id="credentials", data_schema=schema, errors=errors
        )

    async def async_step_zeroconf(self, zeroconf_info):
        """Handle zeroconf discovery."""
        print("async_step_zeroconf: ", zeroconf_info)
        if not zeroconf_info.get("name", "").startswith("Bosch SHC"):
            return self.async_abort(reason="not_shc")

        try:
            self.info = await self._async_get_info(zeroconf_info["host"])
        # except HTTP_CONNECT_ERRORS:
        except Exception:
            return self.async_abort(reason="cannot_connect")
        # except aioshelly.FirmwareUnsupported:
        #     return self.async_abort(reason="unsupported_firmware")

        # await self.async_set_unique_id(info["mac"])
        # self._abort_if_unique_id_configured({CONF_HOST: zeroconf_info["host"]})
        # self.host = zeroconf_info["host"]
        # # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        # self.context["title_placeholders"] = {
        #     "name": _remove_prefix(zeroconf_info["properties"]["id"])
        # }
        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(self, user_input=None):
        """Handle discovery confirm."""
        errors = {}
        print("async_step_confirm_discovery")
        if user_input is not None:
            if self.info["auth"]:
                return await self.async_step_credentials()

            try:
                device_info = await validate_input(self.hass, {})
            # except HTTP_CONNECT_ERRORS:
            #     errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=device_info["title"] or device_info["hostname"],
                    data={"host": self.host},
                )

        return self.async_show_form(
            step_id="confirm_discovery",
            # description_placeholders={
            #     "model": aioshelly.MODEL_NAMES.get(
            #         self.info["type"], self.info["type"]
            #     ),
            #     "host": self.host,
            # },
            errors=errors,
        )

    async def _async_get_info(self, host):
        """Get info from shelly device."""
        print("_async_get_info")

        # async with async_timeout.timeout(5):
        #     return await aioshelly.get_info(
        #         aiohttp_client.async_get_clientsession(self.hass),
        #         host,
        #     )

    # async def async_step_zeroconf(self, discovery_info):
    #     """Prepare configuration for a discovered Bosch SHC device."""
    #     print(discovery_info)
    #     # serial_number = discovery_info["properties"]["macaddress"]

    #     # if serial_number[:6] not in AXIS_OUI:
    #     #     return self.async_abort(reason="not_axis_device")

    #     # if is_link_local(ip_address(discovery_info[CONF_HOST])):
    #     #     return self.async_abort(reason="link_local_address")

    #     # await self.async_set_unique_id(serial_number)

    #     # self._abort_if_unique_id_configured(
    #     #     updates={
    #     #         CONF_HOST: discovery_info[CONF_HOST],
    #     #         CONF_PORT: discovery_info[CONF_PORT],
    #     #     }
    #     # )

    #     # # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
    #     # self.context["title_placeholders"] = {
    #     #     CONF_NAME: discovery_info["hostname"][:-7],
    #     #     CONF_HOST: discovery_info[CONF_HOST],
    #     # }

    #     # self.discovery_schema = {
    #     #     vol.Required(CONF_HOST, default=discovery_info[CONF_HOST]): str,
    #     #     vol.Required(CONF_USERNAME): str,
    #     #     vol.Required(CONF_PASSWORD): str,
    #     #     vol.Required(CONF_PORT, default=discovery_info[CONF_PORT]): int,
    #     # }

    #     # return await self.async_step_user()


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
