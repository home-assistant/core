"""Config flow for devolo Home Network integration."""
import logging
from typing import Dict

from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DeviceNotFound
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components import zeroconf
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_IP_ADDRESS): str})


async def validate_input(
    hass: core.HomeAssistant, data: Dict, discovery_data: Dict = None
):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    zeroconf_instance = await zeroconf.async_get_instance(hass)
    async_client = get_async_client(hass)

    device = Device(
        data[CONF_IP_ADDRESS],
        zeroconf_instance=zeroconf_instance,
        deviceapi=discovery_data,
    )

    await device.async_connect(session_instance=async_client)
    await device.async_disconnect()

    return {
        # TODO Use constants
        "serial_number": device.serial_number,
        "title": device.hostname.split(".")[0],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for devolo Home Network."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Set up the instance."""
        self._discovery_info = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        try:
            info = await validate_input(self.hass, user_input)
        except DeviceNotFound:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info["serial_number"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zerooconf discovery."""
        if discovery_info is None:
            return self.async_abort(reason="cannot_connect")

        if discovery_info["properties"]["MT"] in ["2600", "2601"]:
            return self.async_abort(reason="devolo Home Control Gateway")

        await self.async_set_unique_id(discovery_info["properties"]["SN"])
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {
            "product": discovery_info["properties"]["Product"],
            "name": discovery_info["hostname"].split(".")[0],
        }

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None):
        """Handle a flow initiated by zeroconf."""
        title = self._discovery_info["hostname"].split(".")[0]
        if user_input is not None:
            data = {
                CONF_IP_ADDRESS: self._discovery_info["host"],
            }
            return self.async_create_entry(title=title, data=data)
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"host_name": title},
        )
