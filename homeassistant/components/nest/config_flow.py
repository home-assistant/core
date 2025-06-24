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
from typing import TYPE_CHECKING, Any

from google_nest_sdm.admin_client import (
    DEFAULT_TOPIC_IAM_POLICY,
    AdminClient,
    EligibleSubscriptions,
    EligibleTopics,
)
from google_nest_sdm.exceptions import ApiException
from google_nest_sdm.structure import Structure
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import get_random_string

from . import api
from .const import (
    CONF_CLOUD_PROJECT_ID,
    CONF_PROJECT_ID,
    CONF_SUBSCRIBER_ID_IMPORTED,
    CONF_SUBSCRIPTION_NAME,
    CONF_TOPIC_NAME,
    DATA_SDM,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    SDM_SCOPES,
)

DATA_FLOW_IMPL = "nest_flow_implementation"
TOPIC_FORMAT = "projects/{cloud_project_id}/topics/home-assistant-{rnd}"
SUBSCRIPTION_FORMAT = "projects/{cloud_project_id}/subscriptions/home-assistant-{rnd}"
RAND_LENGTH = 10

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
CREATE_NEW_TOPIC_KEY = "create_new_topic"
CREATE_NEW_SUBSCRIPTION_KEY = "create_new_subscription"

_LOGGER = logging.getLogger(__name__)


def _generate_subscription_id(cloud_project_id: str) -> str:
    """Create a new subscription id."""
    rnd = get_random_string(RAND_LENGTH)
    return SUBSCRIPTION_FORMAT.format(cloud_project_id=cloud_project_id, rnd=rnd)


def _generate_topic_id(cloud_project_id: str) -> str:
    """Create a new topic id."""
    rnd = get_random_string(RAND_LENGTH)
    return TOPIC_FORMAT.format(cloud_project_id=cloud_project_id, rnd=rnd)


def generate_config_title(structures: Iterable[Structure]) -> str | None:
    """Pick a user friendly config title based on the Google Home name(s)."""
    names: list[str] = [
        structure.info.custom_name
        for structure in structures
        if structure.info and structure.info.custom_name
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
        self._admin_client: AdminClient | None = None
        self._eligible_topics: EligibleTopics | None = None
        self._eligible_subscriptions: EligibleSubscriptions | None = None

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
        project_id = self._data.get(CONF_PROJECT_ID)
        query = await super().async_generate_authorize_url()
        authorize_url = OAUTH2_AUTHORIZE.format(project_id=project_id)
        return f"{authorize_url}{query}"

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Complete OAuth setup and finish pubsub or finish."""
        _LOGGER.debug("Finishing post-oauth configuration")
        self._data.update(data)
        _LOGGER.debug("self.source=%s", self.source)
        if self.source == SOURCE_REAUTH:
            _LOGGER.debug("Skipping Pub/Sub configuration")
            return await self._async_finish()
        return await self.async_step_pubsub_topic()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        _LOGGER.debug("async_step_reauth %s", self.source)
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
            self._data[CONF_CLOUD_PROJECT_ID] = user_input[
                CONF_CLOUD_PROJECT_ID
            ].strip()
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
            project_id = user_input[CONF_PROJECT_ID].strip()
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

    async def async_step_pubsub_topic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure and create Pub/Sub topic."""
        cloud_project_id = self._data[CONF_CLOUD_PROJECT_ID]
        if self._admin_client is None:
            access_token = self._data["token"]["access_token"]
            self._admin_client = api.new_pubsub_admin_client(
                self.hass,
                access_token=access_token,
                cloud_project_id=cloud_project_id,
            )
        errors = {}
        if user_input is not None:
            topic_name = user_input[CONF_TOPIC_NAME]
            if topic_name == CREATE_NEW_TOPIC_KEY:
                topic_name = _generate_topic_id(cloud_project_id)
                _LOGGER.debug("Creating topic %s", topic_name)
                try:
                    await self._admin_client.create_topic(topic_name)
                    await self._admin_client.set_topic_iam_policy(
                        topic_name, DEFAULT_TOPIC_IAM_POLICY
                    )
                except ApiException as err:
                    _LOGGER.error("Error creating Pub/Sub topic: %s", err)
                    errors["base"] = "pubsub_api_error"
            if not errors:
                self._data[CONF_TOPIC_NAME] = topic_name
                return await self.async_step_pubsub_topic_confirm()

        device_access_project_id = self._data[CONF_PROJECT_ID]
        try:
            eligible_topics = await self._admin_client.list_eligible_topics(
                device_access_project_id=device_access_project_id
            )
        except ApiException as err:
            _LOGGER.error("Error listing eligible Pub/Sub topics: %s", err)
            return self.async_abort(reason="pubsub_api_error")
        topics = [
            *eligible_topics.topic_names,  # Untranslated topic paths
            CREATE_NEW_TOPIC_KEY,
        ]
        return self.async_show_form(
            step_id="pubsub_topic",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TOPIC_NAME, default=next(iter(topics))
                    ): SelectSelector(
                        SelectSelectorConfig(
                            translation_key="topic_name",
                            mode=SelectSelectorMode.LIST,
                            options=topics,
                        )
                    )
                }
            ),
            description_placeholders={
                "device_access_console_url": DEVICE_ACCESS_CONSOLE_URL,
                "more_info_url": MORE_INFO_URL,
            },
            errors=errors,
        )

    async def async_step_pubsub_topic_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Have the user confirm the Pub/Sub topic is set correctly in Device Access Console."""
        if user_input is not None:
            return await self.async_step_pubsub_subscription()
        return self.async_show_form(
            step_id="pubsub_topic_confirm",
            description_placeholders={
                "device_access_console_url": DEVICE_ACCESS_CONSOLE_EDIT_URL.format(
                    project_id=self._data[CONF_PROJECT_ID]
                ),
                "topic_name": self._data[CONF_TOPIC_NAME],
                "more_info_url": MORE_INFO_URL,
            },
        )

    async def async_step_pubsub_subscription(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure and create Pub/Sub subscription."""
        if TYPE_CHECKING:
            assert self._admin_client
        errors = {}
        if user_input is not None:
            subscription_name = user_input[CONF_SUBSCRIPTION_NAME]
            if subscription_name == CREATE_NEW_SUBSCRIPTION_KEY:
                topic_name = self._data[CONF_TOPIC_NAME]
                subscription_name = _generate_subscription_id(
                    self._data[CONF_CLOUD_PROJECT_ID]
                )
                _LOGGER.debug(
                    "Creating subscription %s on topic %s",
                    subscription_name,
                    topic_name,
                )
                try:
                    await self._admin_client.create_subscription(
                        topic_name,
                        subscription_name,
                    )
                except ApiException as err:
                    _LOGGER.error("Error creatingPub/Sub subscription: %s", err)
                    errors["base"] = "pubsub_api_error"
                else:
                    user_input[CONF_SUBSCRIPTION_NAME] = subscription_name
            else:
                # The user created this subscription themselves so do not delete when removing the integration.
                user_input[CONF_SUBSCRIBER_ID_IMPORTED] = True

            if not errors:
                self._data.update(user_input)
                subscriber = api.new_subscriber_with_token(
                    self.hass,
                    self._data["token"]["access_token"],
                    self._data[CONF_PROJECT_ID],
                    subscription_name,
                )
                try:
                    device_manager = await subscriber.async_get_device_manager()
                except ApiException as err:
                    # Generating a user friendly home name is best effort
                    _LOGGER.debug("Error fetching structures: %s", err)
                else:
                    self._structure_config_title = generate_config_title(
                        device_manager.structures.values()
                    )
                return await self._async_finish()

        subscriptions = []
        try:
            eligible_subscriptions = (
                await self._admin_client.list_eligible_subscriptions(
                    expected_topic_name=self._data[CONF_TOPIC_NAME],
                )
            )
        except ApiException as err:
            _LOGGER.error(
                "Error talking to API to list eligible Pub/Sub subscriptions: %s", err
            )
            errors["base"] = "pubsub_api_error"
        else:
            subscriptions.extend(eligible_subscriptions.subscription_names)
        subscriptions.append(CREATE_NEW_SUBSCRIPTION_KEY)
        return self.async_show_form(
            step_id="pubsub_subscription",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SUBSCRIPTION_NAME,
                        default=next(iter(subscriptions)),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            translation_key="subscription_name",
                            mode=SelectSelectorMode.LIST,
                            options=subscriptions,
                        )
                    )
                }
            ),
            description_placeholders={
                "topic": self._data[CONF_TOPIC_NAME],
                "more_info_url": MORE_INFO_URL,
            },
            errors=errors,
        )

    async def _async_finish(self) -> ConfigFlowResult:
        """Create an entry for the SDM flow."""
        _LOGGER.debug("Creating/updating configuration entry")
        # Update existing config entry when in the reauth flow.
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data=self._data,
            )
        title = self.flow_impl.name
        if self._structure_config_title:
            title = self._structure_config_title
        return self.async_create_entry(title=title, data=self._data)
