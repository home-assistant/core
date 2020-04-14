"""Config flow to configure the IPP integration."""
import logging
from typing import Any, Dict, Optional
from uuid import NAMESPACE_URL, uuid3

from pyipp import (
    IPP,
    IPPConnectionError,
    IPPConnectionUpgradeRequired,
    IPPParseError,
    IPPResponseError,
)
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import CONF_BASE_PATH, CONF_UUID
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistantType, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    ipp = IPP(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        base_path=data[CONF_BASE_PATH],
        tls=data[CONF_SSL],
        verify_ssl=data[CONF_VERIFY_SSL],
        session=session,
    )

    printer = await ipp.printer()

    return {CONF_UUID: printer.info.uuid}


class IPPFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an IPP config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Set up the instance."""
        self.discovery_info = {}

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        try:
            info = await validate_input(self.hass, user_input)
        except IPPConnectionUpgradeRequired:
            return self._show_setup_form({"base": "connection_upgrade"})
        except (IPPConnectionError, IPPResponseError):
            return self._show_setup_form({"base": "connection_error"})
        except IPPParseError:
            _LOGGER.exception("IPP Parse Error")
            return self.async_abort(reason="parse_error")

        unique_id = user_input[CONF_UUID] = info[CONF_UUID]

        if unique_id is None:
            _LOGGER.debug(
                "Printer UUID is missing from IPP info. Falling back to IPP URL"
            )
            # Use the user provided host, port, and base path to build a semi-unique id
            url = f"http://{user_input[CONF_HOST]}:{user_input[CONF_PORT]}{user_input[CONF_BASE_PATH]}"
            unique_id = "url-" + uuid3(NAMESPACE_URL, url).hex

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})

        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    async def async_step_zeroconf(self, discovery_info: ConfigType) -> Dict[str, Any]:
        """Handle zeroconf discovery."""
        # Hostname is format: EPSON123456.local.
        hostname = discovery_info["hostname"].rstrip(".")
        port = discovery_info[CONF_PORT]
        ztype = discovery_info["type"]
        name = discovery_info[CONF_NAME].replace(f".{ztype}", "")
        tls = ztype == "_ipps._tcp.local."
        base_path = discovery_info["properties"].get("rp", "ipp/print")

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update({"title_placeholders": {"name": name}})
        self.discovery_info.update(
            {
                CONF_HOST: discovery_info[CONF_HOST],
                CONF_PORT: port,
                CONF_SSL: tls,
                CONF_VERIFY_SSL: False,
                CONF_BASE_PATH: f"/{base_path}",
                CONF_NAME: name,
                CONF_UUID: discovery_info["properties"].get("UUID"),
            }
        )

        try:
            info = await validate_input(self.hass, self.discovery_info)
        except IPPConnectionUpgradeRequired:
            return self.async_abort(reason="connection_upgrade")
        except (IPPConnectionError, IPPResponseError):
            return self.async_abort(reason="connection_error")
        except IPPParseError:
            _LOGGER.exception("IPP Parse Error")
            return self.async_abort(reason="parse_error")

        unique_id = self.discovery_info[CONF_UUID]
        if unique_id is None and info[CONF_UUID] is not None:
            _LOGGER.debug(
                "Printer UUID is missing from discovery info. Falling back to IPP UUID"
            )
            unique_id = self.discovery_info[CONF_UUID] = info[CONF_UUID]
        elif unique_id is None:
            _LOGGER.debug(
                "Printer UUID is missing from discovery info. Falling back to IPP URL"
            )
            # Use the mdns provided hostname, port, and base path to build a semi-unique id
            # The goal is to allow these printers to be added properly or ignored via UI
            url = f"http://{hostname}:{port}/{base_path}"
            unique_id = "url-" + uuid3(NAMESPACE_URL, url).hex

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self.discovery_info[CONF_HOST],
                CONF_NAME: self.discovery_info[CONF_NAME],
            },
        )

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: ConfigType = None
    ) -> Dict[str, Any]:
        """Handle a confirmation flow initiated by zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"name": self.discovery_info[CONF_NAME]},
                errors={},
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME], data=self.discovery_info,
        )

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=631): int,
                    vol.Required(CONF_BASE_PATH, default="/ipp/print"): str,
                    vol.Required(CONF_SSL, default=False): bool,
                    vol.Required(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors or {},
        )
