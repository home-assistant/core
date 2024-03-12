"""Config flow to configure the LG Soundbar integration."""

import logging
from queue import Empty, Full, Queue

import temescal
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

DATA_SCHEMA = {
    vol.Required(CONF_HOST): str,
}

_LOGGER = logging.getLogger(__name__)

QUEUE_TIMEOUT = 10


def test_connect(host, port):
    """LG Soundbar config flow test_connect."""
    uuid_q = Queue(maxsize=1)
    name_q = Queue(maxsize=1)

    def check_msg_response(response, msgs, attr):
        msg = response["msg"]
        if msg == msgs or msg in msgs:
            if "data" in response and attr in response["data"]:
                return True
            _LOGGER.debug(
                "[%s] msg did not contain expected attr [%s]: %s", msg, attr, response
            )
        return False

    def queue_add(attr_q, data):
        try:
            attr_q.put_nowait(data)
        except Full:
            _LOGGER.debug("attempted to add [%s] to full queue", data)

    def msg_callback(response):
        if check_msg_response(response, ["MAC_INFO_DEV", "PRODUCT_INFO"], "s_uuid"):
            queue_add(uuid_q, response["data"]["s_uuid"])
        if check_msg_response(response, "SPK_LIST_VIEW_INFO", "s_user_name"):
            queue_add(name_q, response["data"]["s_user_name"])

    details = {}

    try:
        connection = temescal.temescal(host, port=port, callback=msg_callback)
        connection.get_info()
        connection.get_mac_info()
        if uuid_q.empty():
            connection.get_product_info()
        details["name"] = name_q.get(timeout=QUEUE_TIMEOUT)
        details["uuid"] = uuid_q.get(timeout=QUEUE_TIMEOUT)
    except Empty:
        pass
    except TimeoutError as err:
        raise ConnectionError(f"Connection timeout with server: {host}:{port}") from err
    except OSError as err:
        raise ConnectionError(f"Cannot resolve hostname: {host}") from err

    return details


class LGSoundbarConfigFlow(ConfigFlow, domain=DOMAIN):
    """LG Soundbar config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_form()

        errors = {}
        try:
            details = await self.hass.async_add_executor_job(
                test_connect, user_input[CONF_HOST], DEFAULT_PORT
            )
        except ConnectionError:
            errors["base"] = "cannot_connect"
        else:
            if len(details) != 0:
                info = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: DEFAULT_PORT,
                }
                if "uuid" in details:
                    unique_id = details["uuid"]
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                else:
                    self._async_abort_entries_match(info)
                return self.async_create_entry(title=details["name"], data=info)
            errors["base"] = "no_data"

        return self._show_form(errors)

    def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(DATA_SCHEMA),
            errors=errors if errors else {},
        )
