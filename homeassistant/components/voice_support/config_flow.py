"""Config flow for the Voice app."""

import asyncio
from typing import Any, override

import aiohttp
import probatio

from homeassistant.components.hassio import AddonError, AddonInfo, AddonState
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .app import (
    DiscoveredApp,
    async_get_discovery,
    async_wait_for_discovery,
    get_app_manager,
)
from .client import VoiceSupportClient
from .const import (
    API_VERSION,
    APP_NAME,
    APP_SLUG,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
    REPOSITORY_URL,
)


def manual_schema(user_input: dict[str, Any]) -> probatio.Schema:
    """Return the schema for the manual address step."""
    return probatio.Schema(
        {
            probatio.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
            probatio.Required(
                CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
            ): probatio.Port(),
        }
    )


class VoiceSupportConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Voice app."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the flow."""
        self._discovery: HassioServiceInfo | None = None
        self._found: DiscoveredApp | None = None
        self._install_task: asyncio.Task[None] | None = None
        self._start_task: asyncio.Task[DiscoveredApp | None] | None = None

    @override
    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle Supervisor discovery."""
        await self.async_set_unique_id(discovery_info.uuid)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: discovery_info.config[CONF_HOST],
                CONF_PORT: discovery_info.config[CONF_PORT],
            }
        )
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered app."""
        assert self._discovery is not None

        if user_input is None:
            return self.async_show_form(
                step_id="hassio_confirm",
                description_placeholders={"name": self._discovery.name},
            )

        return self.async_create_entry(
            title=self._discovery.name,
            data={
                CONF_HOST: self._discovery.config[CONF_HOST],
                CONF_PORT: self._discovery.config[CONF_PORT],
            },
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow started by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if not is_hassio(self.hass):
            return await self.async_step_manual()

        if user_input is None:
            return self.async_show_form(
                step_id="user", description_placeholders={"name": APP_NAME}
            )

        app_info = await self._async_app_info()

        if app_info.state is AddonState.RUNNING:
            return await self.async_step_finish()
        if app_info.state is AddonState.NOT_RUNNING:
            return await self.async_step_start_app()
        if not app_info.available:
            return self.async_abort(
                reason="repository_missing",
                description_placeholders={
                    "name": APP_NAME,
                    "repository": REPOSITORY_URL,
                },
            )
        return await self.async_step_install_app()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up an app at a given address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = VoiceSupportClient(
                self.hass, user_input[CONF_HOST], user_input[CONF_PORT]
            )
            try:
                info = await client.async_update_info()
            except aiohttp.ClientError, TimeoutError, ValueError:
                errors["base"] = "cannot_connect"
            else:
                if info.api_version != API_VERSION:
                    errors["base"] = "unsupported_version"
                else:
                    return self.async_create_entry(
                        title=APP_NAME,
                        data={
                            CONF_HOST: user_input[CONF_HOST],
                            CONF_PORT: user_input[CONF_PORT],
                        },
                    )

        return self.async_show_form(
            step_id="manual",
            data_schema=manual_schema(user_input or {}),
            description_placeholders={"name": APP_NAME},
            errors=errors,
        )

    async def async_step_install_app(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install the app."""
        if self._install_task is None:
            self._install_task = get_app_manager(
                self.hass
            ).async_schedule_install_addon()

        if not self._install_task.done():
            return self.async_show_progress(
                step_id="install_app",
                progress_action="install_app",
                progress_task=self._install_task,
                description_placeholders={"name": APP_NAME},
            )

        try:
            await self._install_task
        except AddonError as err:
            LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="install_failed")
        finally:
            self._install_task = None

        return self.async_show_progress_done(next_step_id="start_app")

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The app could not be installed."""
        return self.async_abort(
            reason="install_failed", description_placeholders={"name": APP_NAME}
        )

    async def async_step_start_app(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the app."""
        if self._start_task is None:
            self._start_task = self.hass.async_create_task(
                self._async_start_and_wait(), eager_start=False
            )

        if not self._start_task.done():
            return self.async_show_progress(
                step_id="start_app",
                progress_action="start_app",
                progress_task=self._start_task,
                description_placeholders={"name": APP_NAME},
            )

        try:
            app = await self._start_task
        except AddonError as err:
            LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="start_failed")
        finally:
            self._start_task = None

        if app is None:
            return self.async_show_progress_done(next_step_id="start_failed")

        self._found = app
        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The app could not be started."""
        return self.async_abort(
            reason="start_failed", description_placeholders={"name": APP_NAME}
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry from the app's discovery or its hostname."""
        app = self._found or await async_get_discovery(self.hass)
        if app is not None:
            await self.async_set_unique_id(app.uuid, raise_on_progress=False)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: app.host, CONF_PORT: app.port}
            )
            return self.async_create_entry(
                title=APP_NAME, data={CONF_HOST: app.host, CONF_PORT: app.port}
            )

        host = (await self._async_app_info()).hostname
        if (host is None) or not await self._async_answers(host, DEFAULT_PORT):
            return self.async_abort(
                reason="no_discovery", description_placeholders={"name": APP_NAME}
            )

        await self.async_set_unique_id(APP_SLUG, raise_on_progress=False)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: host, CONF_PORT: DEFAULT_PORT}
        )
        return self.async_create_entry(
            title=APP_NAME, data={CONF_HOST: host, CONF_PORT: DEFAULT_PORT}
        )

    async def _async_answers(self, host: str, port: int) -> bool:
        """Return if a supported app answers at this address."""
        client = VoiceSupportClient(self.hass, host, port)
        try:
            info = await client.async_update_info()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            LOGGER.debug("Nothing answering at %s: %s", client.url, err)
            return False
        if info.api_version != API_VERSION:
            LOGGER.warning(
                "%s at %s speaks protocol version %s, not %s",
                info.name,
                client.url,
                info.api_version,
                API_VERSION,
            )
            return False
        return True

    async def _async_app_info(self) -> AddonInfo:
        """Return the app's information from the Supervisor."""
        try:
            return await get_app_manager(self.hass).async_get_addon_info()
        except AddonError as err:
            LOGGER.error(err)
            raise AbortFlow(
                "app_info_failed", description_placeholders={"name": APP_NAME}
            ) from err

    async def _async_start_and_wait(self) -> DiscoveredApp | None:
        """Start the app and wait for its discovery message."""
        await get_app_manager(self.hass).async_start_addon()
        return await async_wait_for_discovery(self.hass)
