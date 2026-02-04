"""Config flow for GitHub integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from aiogithubapi import GitHubAPI, GitHubException
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REPOSITORIES, DEFAULT_REPOSITORIES, DOMAIN


async def get_repositories(hass: HomeAssistant, access_token: str) -> list[str]:
    """Return a list of repositories that the user owns or has starred."""
    client = GitHubAPI(token=access_token, session=async_get_clientsession(hass))
    repositories = set()

    async def _get_starred_repositories() -> None:
        response = await client.user.starred(params={"per_page": 100})
        if not response.is_last_page:
            results = await asyncio.gather(
                *(
                    client.user.starred(
                        params={"per_page": 100, "page": page_number},
                    )
                    for page_number in range(
                        response.next_page_number, response.last_page_number + 1
                    )
                )
            )
            for result in results:
                response.data.extend(result.data)

        repositories.update(response.data)

    async def _get_personal_repositories() -> None:
        response = await client.user.repos(params={"per_page": 100})
        if not response.is_last_page:
            results = await asyncio.gather(
                *(
                    client.user.repos(
                        params={"per_page": 100, "page": page_number},
                    )
                    for page_number in range(
                        response.next_page_number, response.last_page_number + 1
                    )
                )
            )
            for result in results:
                response.data.extend(result.data)

        repositories.update(response.data)

    try:
        await asyncio.gather(
            *(
                _get_starred_repositories(),
                _get_personal_repositories(),
            )
        )

    except GitHubException:
        return DEFAULT_REPOSITORIES

    if len(repositories) == 0:
        return DEFAULT_REPOSITORIES

    return sorted(
        (repo.full_name for repo in repositories),
        key=str.casefold,
    )


class GitHubConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for GitHub."""

    DOMAIN = DOMAIN

    VERSION = 1  # Not sure if we need to upgrade this?

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    login_task: asyncio.Task | None = None

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        await self.async_set_unique_id(
            jwt.decode(
                data["token"]["access_token"], options={"verify_signature": False}
            )["sub"]
        )
        self._abort_if_unique_id_configured()
        return await super().async_oauth_create_entry(data)

    async def async_step_repositories(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle repositories step."""

        if TYPE_CHECKING:
            # mypy is not aware that we can't get here without having this set already
            assert self._login is not None

        if not user_input:
            repositories = await get_repositories(self.hass, self._login.access_token)
            return self.async_show_form(
                step_id="repositories",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_REPOSITORIES): cv.multi_select(
                            {k: k for k in repositories}
                        ),
                    }
                ),
            )

        return self.async_create_entry(
            title="",
            data={CONF_ACCESS_TOKEN: self._login.access_token},
            options={CONF_REPOSITORIES: user_input[CONF_REPOSITORIES]},
        )

    async def async_step_could_not_register(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle issues that need transition await from progress step."""
        return self.async_abort(reason="could_not_register")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle a option flow for GitHub."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if not user_input:
            configured_repositories: list[str] = self.config_entry.options[
                CONF_REPOSITORIES
            ]
            repositories = await get_repositories(
                self.hass, self.config_entry.data[CONF_ACCESS_TOKEN]
            )

            # In case the user has removed a starred repository that is already tracked
            for repository in configured_repositories:
                if repository not in repositories:
                    repositories.append(repository)

            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_REPOSITORIES,
                            default=configured_repositories,
                        ): cv.multi_select({k: k for k in repositories}),
                    }
                ),
            )

        return self.async_create_entry(title="", data=user_input)
