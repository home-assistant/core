"""Config flow for SolarEdge."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aiohttp import ClientError, ClientResponseError
import probatio
from solaredge_web import SolarEdgeWeb

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_API_KEY,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SolarEdgeApiError,
    SolarEdgeAuthError,
    SolarEdgeNotFoundError,
    SolarEdgeV2,
)
from .application_credentials import async_register_pending_oauth_flow
from .const import CONF_SECTION_WEB_AUTH, CONF_SITE_ID, DEFAULT_NAME, DOMAIN, LOGGER


class SolarEdgeConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a SolarEdge config flow."""

    VERSION = 2
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._pending_data: dict[str, Any] = {}

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return the logger."""
        return LOGGER

    async def _async_check_web_login(
        self, site_id: str, username: str, password: str
    ) -> str | None:
        """Validate SolarEdge web credentials."""
        api = SolarEdgeWeb(
            username=username,
            password=password,
            site_id=site_id,
            session=async_get_clientsession(self.hass),
        )
        try:
            await api.async_get_equipment()
        except ClientResponseError as err:
            return "invalid_auth" if err.status in (401, 403) else "cannot_connect"
        except TimeoutError, ClientError:
            return "cannot_connect"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the site ID before starting OAuth."""
        errors: dict[str, str] = {}
        if user_input is not None:
            site_id = user_input[CONF_SITE_ID]
            await self.async_set_unique_id(site_id)
            self._abort_if_unique_id_configured()

            web_auth = user_input.get(CONF_SECTION_WEB_AUTH, {})
            if username := web_auth.get(CONF_USERNAME):
                if error := await self._async_check_web_login(
                    site_id, username, web_auth[CONF_PASSWORD]
                ):
                    errors["base"] = error
                else:
                    self._pending_data = {
                        CONF_SITE_ID: site_id,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: web_auth[CONF_PASSWORD],
                    }
            else:
                self._pending_data = {CONF_SITE_ID: site_id}

            if not errors:
                async_register_pending_oauth_flow(self.hass, site_id, self.flow_id)
                return await self.async_step_pick_implementation()

        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_SITE_ID,
                    default=(user_input or {}).get(CONF_SITE_ID, ""),
                ): str,
                probatio.Optional(CONF_SECTION_WEB_AUTH): section(
                    probatio.Schema(
                        {
                            probatio.Inclusive(
                                CONF_USERNAME, "web_account", default=""
                            ): str,
                            probatio.Inclusive(
                                probatio.Secret(CONF_PASSWORD),
                                "web_account",
                                default="",
                            ): str,
                        }
                    ),
                    options={"collapsed": True},
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={
                    CONF_SITE_ID: self._get_reauth_entry().data[CONF_SITE_ID]
                },
            )
        async_register_pending_oauth_flow(
            self.hass,
            self._get_reauth_entry().data[CONF_SITE_ID],
            self.flow_id,
        )
        return await self.async_step_pick_implementation()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure optional module-level web credentials."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            web_auth = user_input.get(CONF_SECTION_WEB_AUTH, {})
            new_data = dict(entry.data)
            new_data.pop(CONF_USERNAME, None)
            new_data.pop(CONF_PASSWORD, None)
            if username := web_auth.get(CONF_USERNAME):
                if error := await self._async_check_web_login(
                    entry.data[CONF_SITE_ID], username, web_auth[CONF_PASSWORD]
                ):
                    errors["base"] = error
                else:
                    new_data[CONF_USERNAME] = username
                    new_data[CONF_PASSWORD] = web_auth[CONF_PASSWORD]
            if not errors:
                return self.async_update_reload_and_abort(entry, data=new_data)

        suggested = {
            CONF_SECTION_WEB_AUTH: {
                CONF_USERNAME: entry.data.get(CONF_USERNAME, ""),
                CONF_PASSWORD: entry.data.get(CONF_PASSWORD, ""),
            }
        }
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_SECTION_WEB_AUTH): section(
                    probatio.Schema(
                        {
                            probatio.Inclusive(
                                CONF_USERNAME, "web_account", default=""
                            ): str,
                            probatio.Inclusive(
                                probatio.Secret(CONF_PASSWORD),
                                "web_account",
                                default="",
                            ): str,
                        }
                    ),
                    options={"collapsed": False},
                )
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or suggested
            ),
            errors=errors,
            description_placeholders={CONF_SITE_ID: entry.data[CONF_SITE_ID]},
        )

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Validate OAuth access and create or update the entry."""
        if self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()
            site_id = entry.data[CONF_SITE_ID]
        else:
            site_id = self._pending_data[CONF_SITE_ID]

        token = data[CONF_TOKEN]

        async def async_get_access_token() -> str:
            return token[CONF_ACCESS_TOKEN]

        api = SolarEdgeV2(async_get_clientsession(self.hass), async_get_access_token)
        try:
            response = await api.get_details(site_id)
            details = response["details"]
        except SolarEdgeAuthError:
            return self.async_abort(reason="oauth_unauthorized")
        except SolarEdgeNotFoundError:
            return self.async_abort(
                reason="wrong_account"
                if self.source == SOURCE_REAUTH
                else "cannot_connect"
            )
        except SolarEdgeApiError, KeyError:
            return self.async_abort(reason="cannot_connect")

        if str(details.get("status", "")).lower() != "active":
            return self.async_abort(reason="site_not_active")

        await self.async_set_unique_id(site_id)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            new_data = {**entry.data, **data, CONF_SITE_ID: site_id}
            new_data.pop(CONF_API_KEY, None)
            return self.async_update_reload_and_abort(entry, data=new_data)

        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=details.get("name") or DEFAULT_NAME,
            data={**self._pending_data, **data},
        )
