"""Config flow to configure Nest.

This configuration flow supports the following:
  - SDM API with Web OAuth flow with redirect back to Home Assistant
  - Legacy Nest API auth flow with where user enters an auth code manually

NestFlowHandler is an implementation of AbstractOAuth2FlowHandler with
some overrides to custom steps inserted in the middle of the flow.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from enum import Enum
import logging
import os
from typing import Any

import async_timeout
from google_nest_sdm.exceptions import (
    ApiException,
    AuthException,
    ConfigurationException,
    SubscriberException,
)
from google_nest_sdm.structure import InfoTrait, Structure
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util import get_random_string
from homeassistant.util.json import JsonObjectType, load_json_object

from . import api
from .const import (
    CONF_CLOUD_PROJECT_ID,
    CONF_PROJECT_ID,
    CONF_SUBSCRIBER_ID,
    DATA_NEST_CONFIG,
    DATA_SDM,
    DOMAIN,
    INSTALLED_AUTH_DOMAIN,
    OAUTH2_AUTHORIZE,
    SDM_SCOPES,
)

DATA_FLOW_IMPL = "nest_flow_implementation"
SUBSCRIPTION_FORMAT = "projects/{cloud_project_id}/subscriptions/home-assistant-{rnd}"
SUBSCRIPTION_RAND_LENGTH = 10

MORE_INFO_URL = "https://www.home-assistant.io/integrations/nest/#configuration"

# URLs for Configure Cloud Project step
CLOUD_CONSOLE_URL = "https://console.cloud.google.com/home/dashboard"
SDM_API_URL = (
    "https://console.cloud.google.com/apis/library/smartdevicemanagement.googleapis.com"
)
PUBSUB_API_URL = "https://console.cloud.google.com/apis/library/pubsub.googleapis.com"

# URLs for Configure Device Access Project step
DEVICE_ACCESS_CONSOLE_URL = "https://console.nest.google.com/device-access/"

# URLs for App Auth deprecation and upgrade
UPGRADE_MORE_INFO_URL = (
    "https://www.home-assistant.io/integrations/nest/#deprecated-app-auth-credentials"
)
DEVICE_ACCESS_CONSOLE_EDIT_URL = (
    "https://console.nest.google.com/device-access/project/{project_id}/information"
)


_LOGGER = logging.getLogger(__name__)


class ConfigMode(Enum):
    """Integration configuration mode."""

    SDM = 1  # SDM api with configuration.yaml
    LEGACY = 2  # "Works with Nest" API
    SDM_APPLICATION_CREDENTIALS = 3  # Config entry only


def get_config_mode(hass: HomeAssistant) -> ConfigMode:
    """Return the integration configuration mode."""
    if DOMAIN not in hass.data or not (
        config := hass.data[DOMAIN].get(DATA_NEST_CONFIG)
    ):
        return ConfigMode.SDM_APPLICATION_CREDENTIALS
    if CONF_PROJECT_ID in config:
        return ConfigMode.SDM
    return ConfigMode.LEGACY


def _generate_subscription_id(cloud_project_id: str) -> str:
    """Create a new subscription id."""
    rnd = get_random_string(SUBSCRIPTION_RAND_LENGTH)
    return SUBSCRIPTION_FORMAT.format(cloud_project_id=cloud_project_id, rnd=rnd)


@callback
def register_flow_implementation(
    hass: HomeAssistant,
    domain: str,
    name: str,
    gen_authorize_url: str,
    convert_code: str,
) -> None:
    """Register a flow implementation for legacy api.

    domain: Domain of the component responsible for the implementation.
    name: Name of the component.
    gen_authorize_url: Coroutine function to generate the authorize url.
    convert_code: Coroutine function to convert a code to an access token.
    """
    if DATA_FLOW_IMPL not in hass.data:
        hass.data[DATA_FLOW_IMPL] = OrderedDict()

    hass.data[DATA_FLOW_IMPL][domain] = {
        "domain": domain,
        "name": name,
        "gen_authorize_url": gen_authorize_url,
        "convert_code": convert_code,
    }


class NestAuthError(HomeAssistantError):
    """Base class for Nest auth errors."""


class CodeInvalid(NestAuthError):
    """Raised when invalid authorization code."""


class UnexpectedStateError(HomeAssistantError):
    """Raised when the config flow is invoked in a 'should not happen' case."""


def generate_config_title(structures: Iterable[Structure]) -> str | None:
    """Pick a user friendly config title based on the Google Home name(s)."""
    names: list[str] = []
    for structure in structures:
        if (trait := structure.traits.get(InfoTrait.NAME)) and trait.custom_name:
            names.append(trait.custom_name)
    if not names:
        return None
    return ", ".join(names)


class NestFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle authentication for both APIs."""

    DOMAIN = DOMAIN
    VERSION = 1

    def __init__(self) -> None:
        """Initialize NestFlowHandler."""
        super().__init__()
        self._upgrade = False
        self._data: dict[str, Any] = {DATA_SDM: {}}
        # Possible name to use for config entry based on the Google Home name
        self._structure_config_title: str | None = None

    @property
    def config_mode(self) -> ConfigMode:
        """Return the configuration type for this flow."""
        return get_config_mode(self.hass)

    def _async_reauth_entry(self) -> ConfigEntry | None:
        """Return existing entry for reauth."""
        if self.source != SOURCE_REAUTH or not (
            entry_id := self.context.get("entry_id")
        ):
            return None
        return next(
            (
                entry
                for entry in self._async_current_entries()
                if entry.entry_id == entry_id
            ),
            None,
        )

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(SDM_SCOPES),
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_generate_authorize_url(self) -> str:
        """Generate a url for the user to authorize based on user input."""
        config = self.hass.data.get(DOMAIN, {}).get(DATA_NEST_CONFIG, {})
        project_id = self._data.get(CONF_PROJECT_ID, config.get(CONF_PROJECT_ID, ""))
        query = await super().async_generate_authorize_url()
        authorize_url = OAUTH2_AUTHORIZE.format(project_id=project_id)
        return f"{authorize_url}{query}"

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Complete OAuth setup and finish pubsub or finish."""
        _LOGGER.debug("Finishing post-oauth configuration")
        assert self.config_mode != ConfigMode.LEGACY, "Step only supported for SDM API"
        self._data.update(data)
        if self.source == SOURCE_REAUTH:
            _LOGGER.debug("Skipping Pub/Sub configuration")
            return await self.async_step_finish()
        return await self.async_step_pubsub()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        assert self.config_mode != ConfigMode.LEGACY, "Step only supported for SDM API"
        self._data.update(entry_data)

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        assert self.config_mode != ConfigMode.LEGACY, "Step only supported for SDM API"
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        if self._data["auth_implementation"] == INSTALLED_AUTH_DOMAIN:
            # The config entry points to an auth mechanism that no longer works and the
            # user needs to take action in the google cloud console to resolve. First
            # prompt to create app creds, then later ensure they've updated the device
            # access console.
            self._upgrade = True
            implementations = await config_entry_oauth2_flow.async_get_implementations(
                self.hass, self.DOMAIN
            )
            if not implementations:
                return await self.async_step_auth_upgrade()
        return await self.async_step_user()

    async def async_step_auth_upgrade(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Give instructions for upgrade of deprecated app auth."""
        assert self.config_mode != ConfigMode.LEGACY, "Step only supported for SDM API"
        if user_input is None:
            return self.async_show_form(
                step_id="auth_upgrade",
                description_placeholders={
                    "more_info_url": UPGRADE_MORE_INFO_URL,
                },
            )
        # Abort this flow and ask the user for application credentials. The frontend
        # will restart a new config flow after the user finishes so schedule a new
        # re-auth config flow for the same entry so the user may resume.
        if reauth_entry := self._async_reauth_entry():
            self.hass.async_add_job(reauth_entry.async_start_reauth, self.hass)
        return self.async_abort(reason="missing_credentials")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self.config_mode == ConfigMode.LEGACY:
            return await self.async_step_init(user_input)
        self._data[DATA_SDM] = {}
        if self.source == SOURCE_REAUTH:
            return await super().async_step_user(user_input)
        # Application Credentials setup needs information from the user
        # before creating the OAuth URL
        return await self.async_step_create_cloud_project()

    async def async_step_create_cloud_project(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle initial step in app credentails flow."""
        implementations = await config_entry_oauth2_flow.async_get_implementations(
            self.hass, self.DOMAIN
        )
        if implementations:
            return await self.async_step_cloud_project()
        # This informational step explains to the user how to setup the
        # cloud console and other pre-requisites needed before setting up
        # an application credential. This extra step also allows discovery
        # to start the config flow rather than aborting. The abort step will
        # redirect the user to the right panel in the UI then return with a
        # valid auth implementation.
        if user_input is not None:
            return self.async_abort(reason="missing_credentials")
        return self.async_show_form(
            step_id="create_cloud_project",
            description_placeholders={
                "cloud_console_url": CLOUD_CONSOLE_URL,
                "sdm_api_url": SDM_API_URL,
                "pubsub_api_url": PUBSUB_API_URL,
                "more_info_url": MORE_INFO_URL,
            },
        )

    async def async_step_cloud_project(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle cloud project in user input."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_device_project()
        return self.async_show_form(
            step_id="cloud_project",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLOUD_PROJECT_ID): str,
                }
            ),
            description_placeholders={
                "cloud_console_url": CLOUD_CONSOLE_URL,
                "more_info_url": MORE_INFO_URL,
            },
        )

    async def async_step_device_project(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Collect device access project from user input."""
        errors = {}
        if user_input is not None:
            project_id = user_input[CONF_PROJECT_ID]
            if project_id == self._data[CONF_CLOUD_PROJECT_ID]:
                _LOGGER.error(
                    "Device Access Project ID and Cloud Project ID must not be the"
                    " same, see documentation"
                )
                errors[CONF_PROJECT_ID] = "wrong_project_id"
            else:
                self._data.update(user_input)
                await self.async_set_unique_id(project_id)
                self._abort_if_unique_id_configured()
                return await super().async_step_user()

        return self.async_show_form(
            step_id="device_project",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROJECT_ID): str,
                }
            ),
            description_placeholders={
                "device_access_console_url": DEVICE_ACCESS_CONSOLE_URL,
                "more_info_url": MORE_INFO_URL,
            },
            errors=errors,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Verify any last pre-requisites before sending user through OAuth flow."""
        if user_input is None and self._upgrade:
            # During app auth upgrade we need the user to update their device
            # access project before we redirect to the authentication flow.
            return await self.async_step_device_project_upgrade()
        return await super().async_step_auth(user_input)

    async def async_step_device_project_upgrade(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Update the device access project."""
        if user_input is not None:
            # Resume OAuth2 redirects
            return await super().async_step_auth()
        if not isinstance(
            self.flow_impl, config_entry_oauth2_flow.LocalOAuth2Implementation
        ):
            raise TypeError(f"Unexpected OAuth implementation: {self.flow_impl}")
        client_id = self.flow_impl.client_id
        return self.async_show_form(
            step_id="device_project_upgrade",
            description_placeholders={
                "device_access_console_url": DEVICE_ACCESS_CONSOLE_EDIT_URL.format(
                    project_id=self._data[CONF_PROJECT_ID]
                ),
                "more_info_url": UPGRADE_MORE_INFO_URL,
                "client_id": client_id,
            },
        )

    async def async_step_pubsub(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure and create Pub/Sub subscriber."""
        data = {
            **self._data,
            **(user_input if user_input is not None else {}),
        }
        cloud_project_id = data.get(CONF_CLOUD_PROJECT_ID, "").strip()
        config = self.hass.data.get(DOMAIN, {}).get(DATA_NEST_CONFIG, {})
        project_id = data.get(CONF_PROJECT_ID, config.get(CONF_PROJECT_ID))

        errors: dict[str, str] = {}
        if cloud_project_id:
            # Create the subscriber id and/or verify it already exists. Note that
            # the existing id is used, and create call below is idempotent
            if not (subscriber_id := data.get(CONF_SUBSCRIBER_ID, "")):
                subscriber_id = _generate_subscription_id(cloud_project_id)
            _LOGGER.debug("Creating subscriber id '%s'", subscriber_id)
            subscriber = api.new_subscriber_with_token(
                self.hass,
                self._data["token"]["access_token"],
                project_id,
                subscriber_id,
            )
            try:
                await subscriber.create_subscription()
            except AuthException as err:
                _LOGGER.error("Subscriber authentication error: %s", err)
                return self.async_abort(reason="invalid_access_token")
            except ConfigurationException as err:
                _LOGGER.error("Configuration error creating subscription: %s", err)
                errors[CONF_CLOUD_PROJECT_ID] = "bad_project_id"
            except SubscriberException as err:
                _LOGGER.error("Error creating subscription: %s", err)
                errors[CONF_CLOUD_PROJECT_ID] = "subscriber_error"
            if not errors:
                try:
                    device_manager = await subscriber.async_get_device_manager()
                except ApiException as err:
                    # Generating a user friendly home name is best effort
                    _LOGGER.debug("Error fetching structures: %s", err)
                else:
                    self._structure_config_title = generate_config_title(
                        device_manager.structures.values()
                    )

                self._data.update(
                    {
                        CONF_SUBSCRIBER_ID: subscriber_id,
                        CONF_CLOUD_PROJECT_ID: cloud_project_id,
                    }
                )
                return await self.async_step_finish()

        return self.async_show_form(
            step_id="pubsub",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLOUD_PROJECT_ID, default=cloud_project_id): str,
                }
            ),
            description_placeholders={"url": CLOUD_CONSOLE_URL},
            errors=errors,
        )

    async def async_step_finish(self, data: dict[str, Any] | None = None) -> FlowResult:
        """Create an entry for the SDM flow."""
        _LOGGER.debug("Creating/updating configuration entry")
        assert self.config_mode != ConfigMode.LEGACY, "Step only supported for SDM API"
        # Update existing config entry when in the reauth flow.
        if entry := self._async_reauth_entry():
            self.hass.config_entries.async_update_entry(
                entry,
                data=self._data,
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        title = self.flow_impl.name
        if self._structure_config_title:
            title = self._structure_config_title
        return self.async_create_entry(title=title, data=self._data)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow start."""
        assert (
            self.config_mode == ConfigMode.LEGACY
        ), "Step only supported for legacy API"

        flows = self.hass.data.get(DATA_FLOW_IMPL, {})

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not flows:
            return self.async_abort(reason="missing_configuration")

        if len(flows) == 1:
            self.flow_impl = list(flows)[0]
            return await self.async_step_link()

        if user_input is not None:
            self.flow_impl = user_input["flow_impl"]
            return await self.async_step_link()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required("flow_impl"): vol.In(list(flows))}),
        )

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Attempt to link with the Nest account.

        Route the user to a website to authenticate with Nest. Depending on
        implementation type we expect a pin or an external component to
        deliver the authentication code.
        """
        assert (
            self.config_mode == ConfigMode.LEGACY
        ), "Step only supported for legacy API"

        flow = self.hass.data[DATA_FLOW_IMPL][self.flow_impl]

        errors = {}

        if user_input is not None:
            try:
                async with async_timeout.timeout(10):
                    tokens = await flow["convert_code"](user_input["code"])
                return self._entry_from_tokens(
                    f"Nest (via {flow['name']})", flow, tokens
                )

            except asyncio.TimeoutError:
                errors["code"] = "timeout"
            except CodeInvalid:
                errors["code"] = "invalid_pin"
            except NestAuthError:
                errors["code"] = "unknown"
            except Exception:  # pylint: disable=broad-except
                errors["code"] = "internal_error"
                _LOGGER.exception("Unexpected error resolving code")

        try:
            async with async_timeout.timeout(10):
                url = await flow["gen_authorize_url"](self.flow_id)
        except asyncio.TimeoutError:
            return self.async_abort(reason="authorize_url_timeout")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error generating auth url")
            return self.async_abort(reason="unknown_authorize_url_generation")

        return self.async_show_form(
            step_id="link",
            description_placeholders={"url": url},
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
        )

    async def async_step_import(self, info: dict[str, Any]) -> FlowResult:
        """Import existing auth from Nest."""
        assert (
            self.config_mode == ConfigMode.LEGACY
        ), "Step only supported for legacy API"

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        config_path = info["nest_conf_path"]

        if not await self.hass.async_add_executor_job(os.path.isfile, config_path):
            self.flow_impl = DOMAIN  # type: ignore[assignment]
            return await self.async_step_link()

        flow = self.hass.data[DATA_FLOW_IMPL][DOMAIN]
        tokens = await self.hass.async_add_executor_job(load_json_object, config_path)

        return self._entry_from_tokens(
            "Nest (import from configuration.yaml)", flow, tokens
        )

    @callback
    def _entry_from_tokens(
        self, title: str, flow: dict[str, Any], tokens: JsonObjectType
    ) -> FlowResult:
        """Create an entry from tokens."""
        return self.async_create_entry(
            title=title, data={"tokens": tokens, "impl_domain": flow["domain"]}
        )
