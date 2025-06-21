"""Config flow for the ntfy integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import random
import re
import string
from typing import TYPE_CHECKING, Any

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
    ATTR_CREDENTIALS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
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
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
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

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Exclusive(CONF_PASSWORD, ATTR_CREDENTIALS): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
        vol.Exclusive(CONF_TOKEN, ATTR_CREDENTIALS): str,
    }
)

STEP_RECONFIGURE_DATA_SCHEMA = vol.Schema(
    {
        vol.Exclusive(CONF_USERNAME, ATTR_CREDENTIALS): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        vol.Optional(CONF_PASSWORD, default=""): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
        vol.Exclusive(CONF_TOKEN, ATTR_CREDENTIALS): str,
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
            username = user_input[SECTION_AUTH].get(CONF_USERNAME)
            self._async_abort_entries_match(
                {
                    CONF_URL: url.human_repr(),
                    CONF_USERNAME: username,
                }
            )
            session = async_get_clientsession(self.hass, user_input[CONF_VERIFY_SSL])
            if username:
                ntfy = Ntfy(
                    user_input[CONF_URL],
                    session,
                    username,
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
                if TYPE_CHECKING:
                    assert url.host
                return self.async_create_entry(
                    title=url.host,
                    data={
                        CONF_URL: url.human_repr(),
                        CONF_USERNAME: username,
                        CONF_TOKEN: token,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}

        entry = self._get_reauth_entry()

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            if token := user_input.get(CONF_TOKEN):
                ntfy = Ntfy(
                    entry.data[CONF_URL],
                    session,
                    token=user_input[CONF_TOKEN],
                )
            else:
                ntfy = Ntfy(
                    entry.data[CONF_URL],
                    session,
                    username=entry.data[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )

            try:
                account = await ntfy.account()
                token = (
                    (await ntfy.generate_token("Home Assistant")).token
                    if not user_input.get(CONF_TOKEN)
                    else user_input[CONF_TOKEN]
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
                if entry.data[CONF_USERNAME] != account.username:
                    return self.async_abort(
                        reason="account_mismatch",
                        description_placeholders={
                            CONF_USERNAME: entry.data[CONF_USERNAME],
                            "wrong_username": account.username,
                        },
                    )
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_REAUTH_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow for ntfy."""
        errors: dict[str, str] = {}

        entry = self._get_reconfigure_entry()

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            if token := user_input.get(CONF_TOKEN):
                ntfy = Ntfy(
                    entry.data[CONF_URL],
                    session,
                    token=user_input[CONF_TOKEN],
                )
            else:
                ntfy = Ntfy(
                    entry.data[CONF_URL],
                    session,
                    username=user_input.get(CONF_USERNAME, entry.data[CONF_USERNAME]),
                    password=user_input[CONF_PASSWORD],
                )

            try:
                account = await ntfy.account()
                if not token:
                    token = (await ntfy.generate_token("Home Assistant")).token
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
                if entry.data[CONF_USERNAME]:
                    if entry.data[CONF_USERNAME] != account.username:
                        return self.async_abort(
                            reason="account_mismatch",
                            description_placeholders={
                                CONF_USERNAME: entry.data[CONF_USERNAME],
                                "wrong_username": account.username,
                            },
                        )

                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={CONF_TOKEN: token},
                    )
                self._async_abort_entries_match(
                    {
                        CONF_URL: entry.data[CONF_URL],
                        CONF_USERNAME: account.username,
                    }
                )
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_USERNAME: account.username,
                        CONF_TOKEN: token,
                    },
                )
        if entry.data[CONF_USERNAME]:
            return self.async_show_form(
                step_id="reconfigure_user",
                data_schema=self.add_suggested_values_to_schema(
                    data_schema=STEP_REAUTH_DATA_SCHEMA,
                    suggested_values=user_input,
                ),
                errors=errors,
                description_placeholders={
                    CONF_NAME: entry.title,
                    CONF_USERNAME: entry.data[CONF_USERNAME],
                },
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_RECONFIGURE_DATA_SCHEMA,
                suggested_values=user_input,
            ),
            errors=errors,
            description_placeholders={CONF_NAME: entry.title},
        )

    async def async_step_reconfigure_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow for authenticated ntfy entry."""

        return await self.async_step_reconfigure(user_input)


class TopicSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a topic."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new topic."""

        return self.async_show_menu(
            step_id="user",
            menu_options=["add_topic", "generate_topic"],
        )

    async def async_step_generate_topic(
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

    async def async_step_add_topic(
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
