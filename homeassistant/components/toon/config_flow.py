"""Config flow to configure the Toon component."""
from collections import OrderedDict
import logging
from functools import partial

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN
from homeassistant.core import callback

from .const import (
    CONF_DISPLAY,
    CONF_TENANT,
    DATA_TOON_CONFIG,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@callback
def configured_displays(hass):
    """Return a set of configured Toon displays."""
    return set(
        entry.data[CONF_DISPLAY] for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class ToonFlowHandler(config_entries.ConfigFlow):
    """Handle a Toon config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the Toon flow."""
        self.displays = None
        self.token = None
        self.tenant = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        app = self.hass.data.get(DATA_TOON_CONFIG, {})

        if not app:
            return self.async_abort(reason="no_app")

        return await self.async_step_authenticate(user_input)

    async def _show_authenticaticate_form(self, errors=None):
        """Show the authentication form to the user."""
        fields = OrderedDict()
        fields[vol.Required(CONF_TOKEN)] = str
        fields[vol.Optional(CONF_TENANT)] = vol.In(["eneco", "electrabel", "viesgo"])

        return self.async_show_form(
            step_id="authenticate",
            data_schema=vol.Schema(fields),
            errors=errors if errors else {},
        )

    async def async_step_authenticate(self, user_input=None):
        """Attempt to authenticate with the Toon account."""
        from toonapilib import Toon
        from toonapilib.toonapilibexceptions import (
            InvalidAuthenticationToken,
            InvalidDisplayName,
            AgreementsRetrievalError,
        )

        if user_input is None:
            return await self._show_authenticaticate_form()

        app = self.hass.data.get(DATA_TOON_CONFIG, {})
        try:
            toon = await self.hass.async_add_executor_job(
                partial(
                    Toon,
                    user_input[CONF_TOKEN],
                    tenant_id=user_input[CONF_TENANT],
                )
            )

            displays = toon.display_names

        except InvalidAuthenticationToken:
            return await self._show_authenticaticate_form({"base": "token"})

        except InvalidDisplayName:
            return await self._show_display_form()

        except AgreementsRetrievalError:
            return self.async_abort(reason="no_agreements")

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error while authenticating")
            return self.async_abort(reason="unknown_auth_fail")

        self.displays = displays
        self.token = user_input[CONF_TOKEN]
        self.tenant = user_input[CONF_TENANT]

        return await self.async_step_display()

    async def _show_display_form(self, errors=None):
        """Show the select display form to the user."""
        fields = OrderedDict()
        fields[vol.Required(CONF_DISPLAY)] = vol.In(self.displays)

        return self.async_show_form(
            step_id="display",
            data_schema=vol.Schema(fields),
            errors=errors if errors else {},
        )

    async def async_step_display(self, user_input=None):
        """Select Toon display to add."""
        from toonapilib import Toon

        if not self.displays:
            return self.async_abort(reason="no_displays")

        if user_input is None:
            return await self._show_display_form()

        if user_input[CONF_DISPLAY] in configured_displays(self.hass):
            return await self._show_display_form({"base": "display_exists"})

        app = self.hass.data.get(DATA_TOON_CONFIG, {})
        try:
            await self.hass.async_add_executor_job(
                partial(
                    Toon,
                    self.token,
                    tenant_id=self.tenant,
                    display_common_name=user_input[CONF_DISPLAY],
                )
            )

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error while authenticating")
            return self.async_abort(reason="unknown_auth_fail")

        return self.async_create_entry(
            title=user_input[CONF_DISPLAY],
            data={
                CONF_TOKEN: self.token,
                CONF_TENANT: self.tenant,
                CONF_DISPLAY: user_input[CONF_DISPLAY],
            },
        )
