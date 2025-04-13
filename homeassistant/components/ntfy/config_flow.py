"""Config flow for the ntfy integration."""

from __future__ import annotations

import logging
import random
import re
import string
from typing import Any

from aiontfy import Ntfy
from aiontfy.exceptions import (
    NtfyException,
    NtfyHTTPError,
    NtfyUnauthorizedAuthenticationError,
)
import voluptuous as vol
from yarl import URL

from homeassistant import data_entry_flow
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_TOPIC, DEFAULT_URL, DOMAIN, SECTION_AUTH

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
                autocomplete="url",
            ),
        ),
        vol.Required(SECTION_AUTH): data_entry_flow.section(
            vol.Schema(
                {
                    vol.Optional(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEXT,
                            autocomplete="username",
                        ),
                    ),
                    vol.Optional(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        ),
                    ),
                }
            ),
            {"collapsed": True},
        ),
    }
)

STEP_USER_TOPIC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOPIC): str,
        vol.Optional(CONF_NAME): str,
    }
)

RE_TOPIC = re.compile("^[-_a-zA-Z0-9]{1,64}$")


class NtfyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ntfy."""

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"topic": TopicSubentryFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = URL(user_input[CONF_URL])
            self._async_abort_entries_match(
                {
                    CONF_URL: url.human_repr(),
                    CONF_USERNAME: user_input[SECTION_AUTH].get(CONF_USERNAME),
                }
            )
            session = async_get_clientsession(self.hass)
            if user_input[SECTION_AUTH].get(CONF_USERNAME):
                ntfy = Ntfy(
                    user_input[CONF_URL],
                    session,
                    user_input[SECTION_AUTH][CONF_USERNAME],
                    user_input[SECTION_AUTH].get(CONF_PASSWORD, ""),
                )
            else:
                ntfy = Ntfy(user_input[CONF_URL], session)

            try:
                account = await ntfy.account()
                token = (
                    (await ntfy.generate_token("Home Assistant")).token
                    if account.username != "*"
                    else None
                )
            except NtfyUnauthorizedAuthenticationError:
                errors["base"] = "invalid_auth"
            except NtfyHTTPError as e:
                _LOGGER.debug("Error %s: %s [%s]", e.code, e.error, e.link)
                errors["base"] = "cannot_connect"
            except NtfyException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=url.host or "",
                    data={
                        CONF_URL: url.human_repr(),
                        CONF_USERNAME: user_input[SECTION_AUTH].get(CONF_USERNAME),
                        CONF_TOKEN: token,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )


class TopicSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a topic."""

    async def async_step_user(  # pylint: disable=hass-return-type
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new topic."""

        return self.async_show_menu(
            step_id="user",
            menu_options=["add_topic", "generate_topic"],
        )

    async def async_step_generate_topic(  # pylint: disable=hass-return-type
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new topic."""
        topic = "".join(
            random.choices(
                string.ascii_lowercase + string.ascii_uppercase + string.digits,
                k=16,
            )
        )
        return self.async_show_form(
            step_id="add_topic",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_TOPIC_SCHEMA,
                suggested_values={CONF_TOPIC: topic},
            ),
        )

    async def async_step_add_topic(  # pylint: disable=hass-return-type
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new topic."""
        config_entry = self._get_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            if not RE_TOPIC.match(user_input[CONF_TOPIC]):
                errors["base"] = "invalid_topic"
            else:
                for existing_subentry in config_entry.subentries.values():
                    if existing_subentry.unique_id == user_input[CONF_TOPIC]:
                        return self.async_abort(reason="already_configured")

                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, user_input[CONF_TOPIC]),
                    data=user_input,
                    unique_id=user_input[CONF_TOPIC],
                )
        return self.async_show_form(
            step_id="add_topic",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_TOPIC_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )
