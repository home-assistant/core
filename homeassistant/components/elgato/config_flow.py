"""Config flow to configure the Elgato Key Light integration."""
import logging
from typing import Any, Dict, Optional

from elgato import Elgato, ElgatoError, Info
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SERIAL_NUMBER, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class ElgatoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Elgato Key Light config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        try:
            info = await self._get_elgato_info(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )
        except ElgatoError:
            return self._show_setup_form({"base": "connection_error"})

        # Check if already configured
        await self.async_set_unique_id(info.serial_number)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=info.serial_number,
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_SERIAL_NUMBER: info.serial_number,
            },
        )

    async def async_step_zeroconf(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle zeroconf discovery."""
        if user_input is None:
            return self.async_abort(reason="connection_error")

        try:
            info = await self._get_elgato_info(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )
        except ElgatoError:
            return self.async_abort(reason="connection_error")

        # Check if already configured
        await self.async_set_unique_id(info.serial_number)
        self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update(
            {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_SERIAL_NUMBER: info.serial_number,
                "title_placeholders": {"serial_number": info.serial_number},
            }
        )

        # Prepare configuration flow
        return self._show_confirm_dialog()

    # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
    async def async_step_zeroconf_confirm(
        self, user_input: ConfigType = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by zeroconf."""
        if user_input is None:
            return self._show_confirm_dialog()

        try:
            info = await self._get_elgato_info(
                self.context.get(CONF_HOST), self.context.get(CONF_PORT)
            )
        except ElgatoError:
            return self.async_abort(reason="connection_error")

        # Check if already configured
        await self.async_set_unique_id(info.serial_number)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self.context.get(CONF_SERIAL_NUMBER),
            data={
                CONF_HOST: self.context.get(CONF_HOST),
                CONF_PORT: self.context.get(CONF_PORT),
                CONF_SERIAL_NUMBER: self.context.get(CONF_SERIAL_NUMBER),
            },
        )

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=9123): int,
                }
            ),
            errors=errors or {},
        )

    def _show_confirm_dialog(self) -> Dict[str, Any]:
        """Show the confirm dialog to the user."""
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        serial_number = self.context.get(CONF_SERIAL_NUMBER)
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"serial_number": serial_number},
        )

    async def _get_elgato_info(self, host: str, port: int) -> Info:
        """Get device information from an Elgato Key Light device."""
        session = async_get_clientsession(self.hass)
        elgato = Elgato(
            host,
            port=port,
            session=session,
        )
        return await elgato.info()
