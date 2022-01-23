"""Config flow to configure Nest.

This configuration flow supports the following:
  - SDM API with Installed app flow where user enters an auth code manually
  - SDM API with Web OAuth flow with redirect back to Home Assistant
  - Legacy Nest API auth flow with where user enters an auth code manually

NestFlowHandler is an implementation of AbstractOAuth2FlowHandler with
some overrides to support installed app and old APIs auth flow, reauth,
and other custom steps inserted in the middle of the flow.

The notable config flow steps are:
- user: To dispatch between API versions
- auth: Inserted to add a hook for the installed app flow to accept a token
- async_oauth_create_entry: Overridden to handle when OAuth is complete.  This
    does not actually create the entry, but holds on to the OAuth token data
    for later
- pubsub: Configure the pubsub subscription. Note that subscriptions created
    by the config flow are deleted when removed.
- finish: Handles creating a new configuration entry or updating the existing
    configuration entry for reauth.

The SDM API config flow supports a hybrid of configuration.yaml (used as defaults)
and config flow.
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

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import get_random_string
from homeassistant.util.json import load_json

from . import api, auth
from .const import (
    CONF_CLOUD_PROJECT_ID,
    CONF_PROJECT_ID,
    CONF_SUBSCRIBER_ID,
    DATA_NEST_CONFIG,
    DATA_SDM,
    DOMAIN,
    INSTALLED_AUTH_DOMAIN,
    OOB_REDIRECT_URI,
    SDM_SCOPES,
)

DATA_FLOW_IMPL = "nest_flow_implementation"
SUBSCRIPTION_FORMAT = "projects/{cloud_project_id}/subscriptions/home-assistant-{rnd}"
SUBSCRIPTION_RAND_LENGTH = 10

MORE_INFO_URL_FORMAT = "https://www.home-assistant.io/integrations/nest/#{anchor}"

# URLs for Configure Cloud Project step
CLOUD_CONSOLE_URL = "https://console.cloud.google.com/home/dashboard"
SDM_API_URL = (
    "https://console.cloud.google.com/apis/library/smartdevicemanagement.googleapis.com"
)
PUBSUB_API_URL = "https://console.cloud.google.com/apis/library/pubsub.googleapis.com"

# URLs for Configure OAuth step
OAUTH_CONSENT_URL_FORMAT = "https://console.cloud.google.com/apis/credentials/consent?project={cloud_project_id}"
OAUTH_CREDS_URL_FORMAT = (
    "https://console.cloud.google.com/apis/credentials?project={cloud_project_id}"
)

# URLs for Configure Device Access Project step
DEVICE_ACCESS_CONSOLE_URL = "https://console.nest.google.com/device-access/"


_LOGGER = logging.getLogger(__name__)


class ConfigMode(Enum):
    """Integration configuration mode."""

    SDM = 1  # SDM api with configuration.yaml
    LEGACY = 2  # "Works with Nest" API
    SDM_CONFIG_ENTRY = 3  # SDM api with config flow / config entry only


def get_config_mode(hass: HomeAssistant) -> ConfigMode:
    """Return the integration configuration mode."""
    if DOMAIN not in hass.data or not (
        config := hass.data[DOMAIN].get(DATA_NEST_CONFIG)
    ):
        return ConfigMode.SDM_CONFIG_ENTRY
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


def register_flow_implementation_from_config(
    hass: HomeAssistant,
    config: ConfigType,
) -> None:
    """Register auth implementations for SDM API from configuration yaml."""
    NestFlowHandler.async_register_implementation(
        hass,
        auth.InstalledAppAuth(
            hass,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            config[DOMAIN][CONF_PROJECT_ID],
        ),
    )
    NestFlowHandler.async_register_implementation(
        hass,
        auth.WebAuth(
            hass,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            config[DOMAIN][CONF_PROJECT_ID],
        ),
    )


def async_register_implementation_from_config_entry(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> None:
    """Register auth implementations from a ConfigEntry data."""
    NestFlowHandler.async_register_implementation(
        hass,
        auth.InstalledAppAuth(
            hass,
            data[CONF_CLIENT_ID],
            data[CONF_CLIENT_SECRET],
            data[CONF_PROJECT_ID],
        ),
    )


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
        self._reauth = False
        self._data: dict[str, Any] = {DATA_SDM: {}}
        # Possible name to use for config entry based on the Google Home name
        self._structure_config_title: str | None = None

    @property
    def config_mode(self) -> ConfigMode:
        """Return the configuration type for this flow."""
        return get_config_mode(self.hass)

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

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Complete OAuth setup and finish pubsub or finish."""
        assert self.config_mode != ConfigMode.LEGACY, "Step only supported for SDM API"
        self._data.update(data)
        if self._reauth or not self._configure_pubsub():
            _LOGGER.debug("Skipping Pub/Sub configuration")
            return await self.async_step_finish()
        return await self.async_step_pubsub()

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        assert self.config_mode != ConfigMode.LEGACY, "Step only supported for SDM API"
        if user_input is None:
            _LOGGER.error("Reauth invoked with empty config entry data")
            return self.async_abort(reason="missing_configuration")
        self._reauth = True
        self._data.update(user_input)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        assert self.config_mode != ConfigMode.LEGACY, "Step only supported for SDM API"
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        existing_entries = self._async_current_entries()
        if existing_entries:
            # Pick an existing auth implementation for Reauth if present. Note
            # only one ConfigEntry is allowed so its safe to pick the first.
            entry = next(iter(existing_entries))
            if "auth_implementation" in entry.data:
                data = {"implementation": entry.data["auth_implementation"]}
                return await super().async_step_user(data)
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self.config_mode == ConfigMode.LEGACY:
            return await self.async_step_init(user_input)
        self._data[DATA_SDM] = {}
        # Reauth will update an existing entry
        entries = self._async_current_entries()
        if entries and not self._reauth:
            return self.async_abort(reason="single_instance_allowed")
        # The SDM mode has authentication implementations registered
        # from yaml at setup time so go right to the user (OAuth) step.
        # The SDM_CONFIG_FLOW version may already have a valid auth
        # implementation registered, however we still need to restart
        # the flow to give the user a chance to update the values in
        # case they entered a mistake.
        if self.config_mode == ConfigMode.SDM:
            return await super().async_step_user(user_input)
        return await self.async_step_cloud_project()

    async def async_step_cloud_project(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle cloud project in user input."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_oauth_input()

        return self.async_show_form(
            step_id="cloud_project",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLOUD_PROJECT_ID): str,
                }
            ),
            description_placeholders={
                "cloud_console_url": CLOUD_CONSOLE_URL,
                "sdm_api_url": SDM_API_URL,
                "pubsub_api_url": PUBSUB_API_URL,
                "more_info_url": MORE_INFO_URL_FORMAT.format(
                    anchor="step_cloud_project"
                ),
            },
        )

    async def async_step_oauth_input(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Create a new OAuth implementation from user input."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_device_project()
        cloud_project_id = self._data[CONF_CLOUD_PROJECT_ID]
        return self.async_show_form(
            step_id="oauth_input",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            description_placeholders={
                "oauth_consent_url": OAUTH_CONSENT_URL_FORMAT.format(
                    cloud_project_id=cloud_project_id
                ),
                "oauth_creds_url": OAUTH_CREDS_URL_FORMAT.format(
                    cloud_project_id=cloud_project_id
                ),
                "more_info_url": MORE_INFO_URL_FORMAT.format(anchor="step_oauth_input"),
            },
        )

    async def async_step_device_project(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Collect device access project from user input."""
        errors = {}
        if user_input is not None:
            if user_input[CONF_PROJECT_ID] == self._data[CONF_CLOUD_PROJECT_ID]:
                _LOGGER.error(
                    "Device Access Project ID and Cloud Project ID must not be the same, see documentation"
                )
                errors[CONF_PROJECT_ID] = "wrong_project_id"
            else:
                self._data.update(user_input)

                # Register an authentication implementation
                async_register_implementation_from_config_entry(self.hass, self._data)

                # Resume authentication flow in the parent class
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
                "oauth_client_id": self._data[CONF_CLIENT_ID],
                "more_info_url": MORE_INFO_URL_FORMAT.format(
                    anchor="step_device_project"
                ),
            },
            errors=errors,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create an entry for auth."""
        if self.flow_impl.domain == INSTALLED_AUTH_DOMAIN:
            # The default behavior from the parent class is to redirect the
            # user with an external step. When using installed app auth, we
            # instead prompt the user to sign in and copy/paste and
            # authentication code back into this form.
            # Note: This is similar to the Legacy API flow below, but it is
            # simpler to reuse the OAuth logic in the parent class than to
            # reuse SDM code with Legacy API code.
            if user_input is not None:
                self.external_data = {
                    "code": user_input["code"],
                    "state": {"redirect_uri": OOB_REDIRECT_URI},
                }
                return await super().async_step_creation(user_input)

            result = await super().async_step_auth()
            return self.async_show_form(
                step_id="auth",
                description_placeholders={
                    "url": result["url"],
                    "more_info_url": MORE_INFO_URL_FORMAT.format(anchor="step_auth"),
                },
                data_schema=vol.Schema({vol.Required("code"): str}),
            )
        return await super().async_step_auth(user_input)

    def _configure_pubsub(self) -> bool:
        """Return True if the config flow should configure Pub/Sub."""
        if self._reauth:
            # Just refreshing tokens and preserving existing subscriber id
            return False
        if self.config_mode == ConfigMode.SDM_CONFIG_ENTRY:
            return True
        # Hard coded in configuration.yaml skips pubsub in config flow
        return CONF_SUBSCRIBER_ID not in self.hass.data.get(DOMAIN, {}).get(
            DATA_NEST_CONFIG, {}
        )

    async def async_step_pubsub(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure and create Pub/Sub subscriber."""
        data = {}
        data.update(self._data)
        if user_input:
            data.update(user_input)
        cloud_project_id = data.get(CONF_CLOUD_PROJECT_ID, "").strip()
        device_access_project_id = data.get(CONF_PROJECT_ID, "")
        if self.config_mode == ConfigMode.SDM:
            device_access_project_id = self.hass.data[DOMAIN][DATA_NEST_CONFIG][
                CONF_PROJECT_ID
            ]
        errors = {}
        if cloud_project_id and cloud_project_id == device_access_project_id:
            _LOGGER.error(
                "Same ID entered for Cloud Project and Device Access Project, these should not be the same"
            )
            errors[CONF_CLOUD_PROJECT_ID] = "wrong_project_id"

        if cloud_project_id and not errors:
            # Create the subscriber id and/or verify it already exists. Note that
            # the existing id is used, and create call below is idempotent
            subscriber_id = data.get(CONF_SUBSCRIBER_ID, "")
            if not subscriber_id:
                subscriber_id = _generate_subscription_id(cloud_project_id)
            _LOGGER.debug("Creating subscriber id '%s'", subscriber_id)
            # Create a placeholder ConfigEntry to use since with the auth we've already created.
            data[CONF_SUBSCRIBER_ID] = subscriber_id
            entry = ConfigEntry(
                version=1, domain=DOMAIN, title="", data=data, source=""
            )
            subscriber = await api.new_subscriber_with_impl(
                self.hass, entry, self.flow_impl
            )
            print(subscriber)
            if not subscriber:
                return self.async_abort(reason="missing_configuration")
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
        assert self.config_mode != ConfigMode.LEGACY, "Step only supported for SDM API"
        await self.async_set_unique_id(DOMAIN)
        # Update existing config entry when in the reauth flow.  This
        # integration only supports one config entry so remove any prior entries
        # added before the "single_instance_allowed" check was added
        existing_entries = self._async_current_entries()
        if existing_entries:
            updated = False
            for entry in existing_entries:
                if updated:
                    await self.hass.config_entries.async_remove(entry.entry_id)
                    continue
                updated = True
                self.hass.config_entries.async_update_entry(
                    entry, data=self._data, unique_id=DOMAIN
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
            self.flow_impl = DOMAIN  # type: ignore
            return await self.async_step_link()

        flow = self.hass.data[DATA_FLOW_IMPL][DOMAIN]
        tokens = await self.hass.async_add_executor_job(load_json, config_path)

        return self._entry_from_tokens(
            "Nest (import from configuration.yaml)", flow, tokens
        )

    @callback
    def _entry_from_tokens(
        self, title: str, flow: dict[str, Any], tokens: list[Any] | dict[Any, Any]
    ) -> FlowResult:
        """Create an entry from tokens."""
        return self.async_create_entry(
            title=title, data={"tokens": tokens, "impl_domain": flow["domain"]}
        )
