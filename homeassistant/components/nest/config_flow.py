"""Config flow to configure Nest.

This configuration flow supports the following:
  - SDM API with Web OAuth flow with redirect back to Home Assistant
  - Legacy Nest API auth flow with where user enters an auth code manually

NestFlowHandler is an implementation of AbstractOAuth2FlowHandler with
some overrides to custom steps inserted in the middle of the flow.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from typing import Any

from google_nest_sdm.exceptions import (
    ApiException,
    AuthException,
    ConfigurationException,
    SubscriberException,
)
from google_nest_sdm.structure import InfoTrait, Structure
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util import get_random_string

from . import api
from .const import (
    CONF_CLOUD_PROJECT_ID,
    CONF_PROJECT_ID,
    CONF_SUBSCRIBER_ID,
    DATA_NEST_CONFIG,
    DATA_SDM,
    DOMAIN,
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

DEVICE_ACCESS_CONSOLE_EDIT_URL = (
    "https://console.nest.google.com/device-access/project/{project_id}/information"
)


_LOGGER = logging.getLogger(__name__)


def _generate_subscription_id(cloud_project_id: str) -> str:
    """Create a new subscription id."""
    rnd = get_random_string(SUBSCRIPTION_RAND_LENGTH)
    return SUBSCRIPTION_FORMAT.format(cloud_project_id=cloud_project_id, rnd=rnd)


def generate_config_title(structures: Iterable[Structure]) -> str | None:
    """Pick a user friendly config title based on the Google Home name(s)."""
    names: list[str] = [
        trait.custom_name
        for structure in structures
        if (trait := structure.traits.get(InfoTrait.NAME)) and trait.custom_name
    ]
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
        self._data: dict[str, Any] = {DATA_SDM: {}}
        # Possible name to use for config entry based on the Google Home name
        self._structure_config_title: str | None = None

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

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Complete OAuth setup and finish pubsub or finish."""
        _LOGGER.debug("Finishing post-oauth configuration")
        self._data.update(data)
        if self.source == SOURCE_REAUTH:
            _LOGGER.debug("Skipping Pub/Sub configuration")
            return await self.async_step_finish()
        return await self.async_step_pubsub()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self._data.update(entry_data)

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        self._data[DATA_SDM] = {}
        if self.source == SOURCE_REAUTH:
            return await super().async_step_user(user_input)
        # Application Credentials setup needs information from the user
        # before creating the OAuth URL
        return await self.async_step_create_cloud_project()

    async def async_step_create_cloud_project(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial step in app credentials flow."""
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
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
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

    async def async_step_pubsub(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

    async def async_step_finish(
        self, data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create an entry for the SDM flow."""
        _LOGGER.debug("Creating/updating configuration entry")
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
