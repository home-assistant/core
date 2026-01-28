"""Config flow for GitHub integration."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from aiogithubapi import (
    GitHubAPI,
    GitHubDeviceAPI,
    GitHubException,
    GitHubLoginDeviceModel,
    GitHubLoginOauthModel,
)
from aiogithubapi.const import OAUTH_USER_LOGIN
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import (
    SERVER_SOFTWARE,
    async_get_clientsession,
)
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import (
    CLIENT_ID,
    CONF_REPOSITORY,
    DEFAULT_REPOSITORIES,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_REPOSITORY,
)


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


class GitHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GitHub."""

    VERSION = 1

    login_task: asyncio.Task | None = None

    def __init__(self) -> None:
        """Initialize."""
        self._device: GitHubDeviceAPI | None = None
        self._login: GitHubLoginOauthModel | None = None
        self._login_device: GitHubLoginDeviceModel | None = None

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_TYPE_REPOSITORY: RepositoryFlowHandler}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return await self.async_step_device(user_input)

    async def async_step_device(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle device steps."""

        async def _wait_for_login() -> None:
            if TYPE_CHECKING:
                # mypy is not aware that we can't get here without having these set already
                assert self._device is not None
                assert self._login_device is not None

            response = await self._device.activation(
                device_code=self._login_device.device_code
            )
            self._login = response.data

        if not self._device:
            self._device = GitHubDeviceAPI(
                client_id=CLIENT_ID,
                session=async_get_clientsession(self.hass),
                client_name=SERVER_SOFTWARE,
            )

            try:
                response = await self._device.register()
                self._login_device = response.data
            except GitHubException as exception:
                LOGGER.exception(exception)
                return self.async_abort(reason="could_not_register")

        if self.login_task is None:
            self.login_task = self.hass.async_create_task(_wait_for_login())

        if self.login_task.done():
            if self.login_task.exception():
                return self.async_show_progress_done(next_step_id="could_not_register")
            return self.async_show_progress_done(next_step_id="done")

        if TYPE_CHECKING:
            # mypy is not aware that we can't get here without having this set already
            assert self._login_device is not None

        return self.async_show_progress(
            step_id="device",
            progress_action="wait_for_device",
            description_placeholders={
                "url": OAUTH_USER_LOGIN,
                "code": self._login_device.user_code,
            },
            progress_task=self.login_task,
        )

    async def async_step_done(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle repositories step."""

        if TYPE_CHECKING:
            assert self._login is not None

        return self.async_create_entry(
            title="",
            data={CONF_ACCESS_TOKEN: self._login.access_token},
        )

    async def async_step_could_not_register(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle issues that need transition await from progress step."""
        return self.async_abort(reason="could_not_register")


class RepositoryFlowHandler(ConfigSubentryFlow):
    """Handle repository subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle options flow."""
        if not user_input:
            repositories = await get_repositories(
                self.hass, self._get_entry().data[CONF_ACCESS_TOKEN]
            )

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_REPOSITORY): SelectSelector(
                            SelectSelectorConfig(sort=True, options=repositories)
                        ),
                    }
                ),
            )
        repository = user_input[CONF_REPOSITORY]

        for subentry in self._get_entry().subentries.values():
            if subentry.unique_id == repository:
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title=user_input[CONF_REPOSITORY], data=user_input, unique_id=repository
        )
