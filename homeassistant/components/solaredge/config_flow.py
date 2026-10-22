"""Config flow for the SolarEdge platform."""

from collections.abc import Mapping
import logging
import socket
from typing import TYPE_CHECKING, Any, override

from aiohttp import ClientError, ClientResponseError
import aiosolaredge
from aiosolaredge.v2 import RateLimitError, SolarEdgeV2, SolarEdgeV2Error
import probatio
from solaredge_web import SolarEdgeWeb

from homeassistant.components.application_credentials import (
    DATA_COMPONENT,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_entry_oauth2_flow as oauth
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from .const import (
    CONF_SECTION_API_AUTH,
    CONF_SECTION_WEB_AUTH,
    CONF_SITE_ID,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
)
from .oauth_callback import CALLBACK_VALIDATED, async_register_pending
from .v2_budget import get_budget
from .v2_runtime import async_repair_authorization, safe_metadata


class SolarEdgeConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._errors: dict[str, str] = {}
        self._oauth_site_id = ""
        # Validated web-account change, applied only once consent succeeds.
        # None keeps the existing settings; an empty dict clears them.
        self._pending_web: dict[str, str] | None = None

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return the integration logger."""
        return LOGGER

    @override
    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Only the validated provider-specific callback may resume consent."""
        if user_input is not None:
            if user_input.pop("solaredge_callback", None) is not CALLBACK_VALIDATED:
                return await super().async_step_auth({"error": "invalid_callback"})
        return await super().async_step_auth(user_input)

    @property
    def oauth_site_id(self) -> str:
        """Return the site bound to this consent flow, never callback metadata."""
        return self._oauth_site_id

    @override
    async def async_generate_authorize_url(self) -> str:
        """Bind the provider callback to this exact pending native flow."""
        url = await super().async_generate_authorize_url()
        async_register_pending(self.hass, self, url, self._oauth_site_id)
        return url

    @callback
    def _async_current_site_ids(self) -> set[str]:
        """Return the site_ids for the domain."""
        return {
            entry.data[CONF_SITE_ID]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_SITE_ID in entry.data
        }

    def _site_in_configuration_exists(self, site_id: str) -> bool:
        """Return True if site_id exists in configuration."""
        return site_id in self._async_current_site_ids()

    async def _async_check_site(self, site_id: str, api_key: str) -> bool:
        """Check if we can connect to the soleredge api service."""
        session = async_get_clientsession(self.hass)
        api = aiosolaredge.SolarEdge(api_key, session)
        try:
            response = await api.get_details(site_id)
            if response["details"]["status"].lower() != "active":
                self._errors[CONF_SITE_ID] = "site_not_active"
                return False
        except TimeoutError, ClientError, socket.gaierror:
            self._errors[CONF_SITE_ID] = "cannot_connect"
            return False
        except KeyError:
            self._errors[CONF_SITE_ID] = "invalid_api_key"
            return False
        return True

    async def _async_check_web_login(
        self, site_id: str, username: str, password: str
    ) -> bool:
        """Validate the user input allows us to connect to the web service."""
        api = SolarEdgeWeb(
            username=username,
            password=password,
            site_id=site_id,
            session=async_get_clientsession(self.hass),
        )
        try:
            await api.async_get_equipment()
        except ClientResponseError as err:
            if err.status in (401, 403):
                self._errors["base"] = "invalid_auth"
            else:
                self._errors["base"] = "cannot_connect"
            return False
        except TimeoutError, ClientError:
            self._errors["base"] = "cannot_connect"
            return False
        return True

    async def _async_stage_web_update(
        self, site_id: str, user_input: dict[str, Any]
    ) -> bool:
        """Validate submitted web credentials before consent; save nothing yet."""
        self._pending_web = None
        if CONF_SECTION_WEB_AUTH not in user_input:
            return True
        web_auth = user_input[CONF_SECTION_WEB_AUTH]
        if not (username := web_auth.get(CONF_USERNAME)):
            self._pending_web = {}
            return True
        if not await self._async_check_web_login(
            site_id, username, web_auth[CONF_PASSWORD]
        ):
            return False
        self._pending_web = {
            CONF_USERNAME: username,
            CONF_PASSWORD: web_auth[CONF_PASSWORD],
        }
        return True

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes an integration or reconfigures it."""
        self._errors = {}
        entry = None
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()

        current_oauth = entry is not None and entry.data.get("api_version") == 2
        use_oauth = (
            user_input.get("use_oauth", current_oauth)
            if user_input is not None
            else current_oauth
        )
        keep_oauth = current_oauth and use_oauth
        if user_input is not None and use_oauth and not keep_oauth:
            site_id = entry.data[CONF_SITE_ID] if entry else user_input[CONF_SITE_ID]
            if not site_id.isascii() or not site_id.isdecimal():
                return self.async_abort(reason="invalid_site")
            if await self._async_stage_web_update(site_id, user_input):
                self._oauth_site_id = site_id
                return await self.async_step_oauth_application()
        elif user_input is not None:
            name = slugify(user_input.get(CONF_NAME, DEFAULT_NAME))
            if self.source == SOURCE_RECONFIGURE:
                if TYPE_CHECKING:
                    assert entry
                site_id = entry.data[CONF_SITE_ID]
            else:
                site_id = user_input[CONF_SITE_ID]
            api_auth = user_input.get(CONF_SECTION_API_AUTH, {})
            web_auth = user_input.get(CONF_SECTION_WEB_AUTH, {})
            api_key = api_auth.get(CONF_API_KEY)
            username = web_auth.get(CONF_USERNAME)

            if self.source != SOURCE_RECONFIGURE and self._site_in_configuration_exists(
                site_id
            ):
                self._errors[CONF_SITE_ID] = "already_configured"
            elif keep_oauth and api_key:
                # Never merge a V1 key into a kept V2 entry; switching is explicit.
                self._errors["base"] = "api_key_with_oauth"
            elif current_oauth and not use_oauth and not api_key:
                # Web credentials alone are not explicit, validated V1 API intent.
                self._errors["base"] = "v1_api_key_required"
            elif not keep_oauth and not api_key and not username:
                self._errors["base"] = "auth_missing"
            else:
                api_key_ok = True
                if api_key:
                    api_key_ok = await self._async_check_site(site_id, api_key)

                web_login_ok = True
                if api_key_ok and username:
                    web_login_ok = await self._async_check_web_login(
                        site_id, username, web_auth[CONF_PASSWORD]
                    )

                if api_key_ok and web_login_ok:
                    # A web-only V2 edit keeps the native OAuth context; only the
                    # submitted web credentials replace (or clear) the previous ones.
                    data = (
                        {
                            key: value
                            for key, value in entry.data.items()
                            if key not in (CONF_USERNAME, CONF_PASSWORD)
                        }
                        if keep_oauth and entry
                        else {}
                    )
                    data[CONF_SITE_ID] = site_id
                    if api_key:
                        data[CONF_API_KEY] = api_key
                    if username:
                        data[CONF_USERNAME] = username
                        data[CONF_PASSWORD] = web_auth[CONF_PASSWORD]

                    if self.source == SOURCE_RECONFIGURE:
                        if TYPE_CHECKING:
                            assert entry
                        return self.async_update_reload_and_abort(entry, data=data)

                    return self.async_create_entry(title=name, data=data)
        elif self.source == SOURCE_RECONFIGURE:
            if TYPE_CHECKING:
                assert entry
            user_input = {
                "use_oauth": current_oauth,
                CONF_SECTION_API_AUTH: {CONF_API_KEY: entry.data.get(CONF_API_KEY, "")},
                CONF_SECTION_WEB_AUTH: {
                    CONF_USERNAME: entry.data.get(CONF_USERNAME, ""),
                    CONF_PASSWORD: entry.data.get(CONF_PASSWORD, ""),
                },
            }
        else:
            user_input = {}

        data_schema_dict: dict[probatio.Marker, Any] = {
            probatio.Optional("use_oauth", default=current_oauth): bool
        }
        if self.source != SOURCE_RECONFIGURE:
            data_schema_dict[
                # Name field is no longer allowed in config flow schemas
                # pylint: disable-next=home-assistant-config-flow-name-field
                probatio.Required(
                    CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                )
            ] = str
            data_schema_dict[
                probatio.Required(
                    CONF_SITE_ID, default=user_input.get(CONF_SITE_ID, "")
                )
            ] = str

        data_schema_dict.update(
            {
                probatio.Optional(CONF_SECTION_API_AUTH): section(
                    probatio.Schema(
                        {
                            probatio.Optional(
                                probatio.Secret(CONF_API_KEY), default=""
                            ): str,
                        }
                    ),
                    options={"collapsed": False},
                ),
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
                ),
            }
        )
        data_schema = probatio.Schema(data_schema_dict)

        step_id = "user"
        description_placeholders = {}
        if self.source == SOURCE_RECONFIGURE:
            if TYPE_CHECKING:
                assert entry
            step_id = "reconfigure"
            description_placeholders["site_id"] = entry.data[CONF_SITE_ID]

        # pylint: disable-next=home-assistant-step_id-match-method
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, user_input),
            errors=self._errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_oauth_application(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect missing application credentials without restarting this flow."""
        if user_input is None and await oauth.async_get_implementations(
            self.hass, DOMAIN
        ):
            return await self.async_step_pick_implementation()
        errors: dict[str, str] = {}
        if user_input is not None:
            client_id = user_input.get(CONF_CLIENT_ID, "").strip()
            client_secret = user_input.get(CONF_CLIENT_SECRET, "").strip()
            if not client_id or not client_secret:
                errors["base"] = "oauth_credentials_required"
            else:
                credentials = self.hass.data[DATA_COMPONENT].async_client_credentials(
                    DOMAIN
                )
                auth_domain = slugify(f"{DOMAIN}.{client_id}")
                for domain, credential in credentials.items():
                    if credential.client_id == client_id:
                        if credential.client_secret != client_secret:
                            errors["base"] = "oauth_credentials_conflict"
                        else:
                            return await self.async_step_pick_implementation(
                                {"implementation": domain}
                            )
                        break
                if auth_domain in credentials:
                    errors["base"] = "oauth_credentials_conflict"
                if not errors:
                    await async_import_client_credential(
                        self.hass,
                        DOMAIN,
                        ClientCredential(client_id, client_secret, name=DEFAULT_NAME),
                        auth_domain=auth_domain,
                    )
                    return await self.async_step_pick_implementation(
                        {"implementation": auth_domain}
                    )
        return self.async_show_form(
            step_id="oauth_application",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(CONF_CLIENT_ID): TextSelector(),
                    probatio.Optional(
                        probatio.Secret(CONF_CLIENT_SECRET)
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initiated by the user."""
        return await self.async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Renew the grant without creating a new config entry."""
        self._oauth_site_id = entry_data[CONF_SITE_ID]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the limited Basic mode before linking."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_oauth_application()

    @override
    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Bind typed site ID to authenticated site metadata, never callback input."""

        async def access_token() -> str:
            return data["token"]["access_token"]

        budget = get_budget(self.hass)
        api = SolarEdgeV2(
            async_get_clientsession(self.hass), access_token, budget.reserve
        )
        try:
            metadata = await api.site(self._oauth_site_id)
        except RateLimitError as err:
            if err.http_status == 429:
                # Local reservation refusals must not extend the shared deadline.
                await budget.pause(err)
            return self.async_abort(reason="cannot_connect")
        except SolarEdgeV2Error:
            return self.async_abort(reason="cannot_connect")
        if str(metadata.get("siteId")) != self._oauth_site_id:
            return self.async_abort(reason="invalid_site")
        data.update(
            {
                CONF_SITE_ID: self._oauth_site_id,
                "api_version": 2,
                "site_metadata": safe_metadata(metadata),
            }
        )
        if self.source in ("reauth", SOURCE_RECONFIGURE):
            entry = (
                self._get_reauth_entry()
                if self.source == "reauth"
                else self._get_reconfigure_entry()
            )
            updated = {**entry.data, **data}
            updated.pop(CONF_API_KEY, None)
            if self._pending_web is not None:
                updated.pop(CONF_USERNAME, None)
                updated.pop(CONF_PASSWORD, None)
                updated.update(self._pending_web)
            await async_repair_authorization(
                self.hass, entry.entry_id, safe_metadata(metadata)
            )
            return self.async_update_reload_and_abort(entry, data=updated)
        if self._site_in_configuration_exists(self._oauth_site_id):
            return self.async_abort(reason="already_configured")
        return self.async_create_entry(
            title=DEFAULT_NAME, data={**data, **(self._pending_web or {})}
        )
