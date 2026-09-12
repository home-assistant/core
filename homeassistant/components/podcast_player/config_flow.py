"""Config flow for Podcast Player."""

import logging
from typing import Any, override

from aiopodcast import (
    Podcast,
    PodcastConnectionError,
    PodcastFeedError,
    PodcastHTTPError,
)
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import create_client
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL, autocomplete="url")
        )
    }
)


class InvalidUrl(HomeAssistantError):
    """Error to indicate an invalid feed URL."""


def normalize_url(value: str) -> str:
    """Validate and normalize a podcast feed URL."""
    try:
        url = URL(value)
    except ValueError as err:
        raise InvalidUrl from err

    if (
        url.scheme not in {"http", "https"}
        or url.host is None
        or url.user is not None
        or url.password is not None
    ):
        raise InvalidUrl

    return str(url.with_fragment(None))


async def async_validate_input(hass: HomeAssistant, url: str) -> Podcast:
    """Fetch and validate a podcast feed."""
    return await create_client(hass).async_fetch(url)


class PodcastPlayerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Podcast Player."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                url = normalize_url(user_input[CONF_URL])
            except InvalidUrl:
                errors[CONF_URL] = "invalid_url"
            else:
                self._async_abort_entries_match({CONF_URL: url})
                try:
                    podcast = await async_validate_input(self.hass, url)
                    canonical_url = normalize_url(podcast.canonical_url)
                except PodcastConnectionError, PodcastHTTPError:
                    errors["base"] = "cannot_connect"
                except PodcastFeedError, InvalidUrl:
                    errors["base"] = "invalid_feed"
                except Exception:
                    _LOGGER.exception(
                        "Unexpected exception while validating podcast feed"
                    )
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(canonical_url)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=podcast.title,
                        data={CONF_URL: url},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
