"""Config flow for the Voice support integration."""

import asyncio
from collections.abc import Callable, Coroutine
import logging
from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.components.hassio import AddonError, AddonState
from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import async_is_enabled
from .app import get_app_manager
from .client import CLIENT_ERRORS, AppInfo, UnsupportedVersionError, VoiceSupportClient
from .const import CONF_INTEGRATION_CREATED_APP, DOMAIN

CONF_USE_APP = "use_app"

DEFAULT_PORT = 10900

APP_START_INTERVAL = 5
APP_START_ROUNDS = 40

ISSUE_APP_SETUP_FAILED = "app_setup_failed"

_LOGGER = logging.getLogger(__name__)

STEP_MANUAL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)
STEP_ON_SUPERVISOR_SCHEMA = probatio.Schema(
    {probatio.Optional(CONF_USE_APP, default=True): bool}
)


async def _async_get_info(hass: HomeAssistant, host: str, port: int) -> AppInfo:
    """Ask the app at this address what it is."""
    return await VoiceSupportClient(hass, host, port).async_update_info()


class VoiceSupportConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Voice support."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up flow instance."""
        self._host: str | None = None
        self._port: int | None = None
        self._info: AppInfo | None = None
        self._running_in_background = False
        self._integration_created_app = False
        self._failure: str | None = None
        self._install_task: asyncio.Task[None] | None = None
        self._start_task: asyncio.Task[None] | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if not async_is_enabled(self.hass):
            return self.async_abort(reason="preview_feature_disabled")
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if is_hassio(self.hass):
            return await self.async_step_on_supervisor()
        return await self.async_step_manual()

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set the app up without a person in the loop."""
        if not async_is_enabled(self.hass):
            return self.async_abort(reason="preview_feature_disabled")
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        self._running_in_background = True
        return await self.async_step_on_supervisor({CONF_USE_APP: True})

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manual configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host: str = user_input[CONF_HOST]
            port: int = user_input[CONF_PORT]
            try:
                self._info = await _async_get_info(self.hass, host, port)
            except CLIENT_ERRORS:
                errors["base"] = "cannot_connect"
            except UnsupportedVersionError:
                errors["base"] = "unsupported_version"
            else:
                self._host = host
                self._port = port
                return self._async_create_entry()

        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(
                STEP_MANUAL_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle logic when on Supervisor host."""
        if user_input is not None:
            if not user_input[CONF_USE_APP]:
                return await self.async_step_manual()

            try:
                app_info = await get_app_manager(self.hass).async_get_addon_info()
            except AddonError as err:
                _LOGGER.error(err)
                return self._async_fail("app_info_failed")

            if app_info.state is AddonState.RUNNING:
                return await self.async_step_finish_app_setup()
            if app_info.state is AddonState.NOT_RUNNING:
                return await self.async_step_start_app()
            return await self.async_step_install_app()

        return self.async_show_form(
            step_id="on_supervisor", data_schema=STEP_ON_SUPERVISOR_SCHEMA
        )

    async def async_step_install_app(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install the Voice app."""
        if self._install_task is None:
            self._install_task = get_app_manager(
                self.hass
            ).async_schedule_install_addon()

        if not self._running_in_background and not self._install_task.done():
            return self.async_show_progress(
                step_id="install_app",
                progress_action="install_app",
                progress_task=self._install_task,
            )

        try:
            await self._install_task
        except AddonError as err:
            _LOGGER.error(err)
            return await self._async_progress_failed("app_install_failed")
        finally:
            self._install_task = None

        self._integration_created_app = True
        return await self._async_progress_done(self.async_step_start_app)

    async def async_step_start_app(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the Voice app."""
        if self._start_task is None:
            self._start_task = self.hass.async_create_task(self._async_start_app())

        if not self._running_in_background and not self._start_task.done():
            return self.async_show_progress(
                step_id="start_app",
                progress_action="start_app",
                progress_task=self._start_task,
            )

        try:
            await self._start_task
        except (AddonError, TimeoutError) as err:
            _LOGGER.error(err)
            return await self._async_progress_failed("app_start_failed")
        except UnsupportedVersionError as err:
            _LOGGER.error(err)
            return await self._async_progress_failed("unsupported_version")
        finally:
            self._start_task = None

        return await self._async_progress_done(self.async_step_finish_app_setup)

    async def async_step_finish_app_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry for the running app."""
        if self._info is None:
            try:
                await self._async_connect_app()
            except AddonError as err:
                _LOGGER.error(err)
                return self._async_fail("app_get_discovery_info_failed")
            except CLIENT_ERRORS:
                return self._async_fail("cannot_connect")
            except UnsupportedVersionError as err:
                _LOGGER.error(err)
                return self._async_fail("unsupported_version")

        return self._async_create_entry()

    async def async_step_app_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort with what went wrong in the progress step before."""
        if TYPE_CHECKING:
            assert self._failure is not None
        return self._async_fail(self._failure)

    async def _async_progress_done(
        self, next_step: Callable[[], Coroutine[Any, Any, ConfigFlowResult]]
    ) -> ConfigFlowResult:
        """Move on from a progress step, directly when nobody is watching."""
        if self._running_in_background:
            return await next_step()
        return self.async_show_progress_done(
            next_step_id=next_step.__name__.removeprefix("async_step_")
        )

    async def _async_progress_failed(self, reason: str) -> ConfigFlowResult:
        """Give up on a progress step, directly when nobody is watching."""
        if self._running_in_background:
            return self._async_fail(reason)
        self._failure = reason
        return self.async_show_progress_done(next_step_id="app_failed")

    @callback
    def _async_fail(self, reason: str) -> ConfigFlowResult:
        """Abort, and leave a repair issue when nobody is watching the flow."""
        if self._running_in_background:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_APP_SETUP_FAILED,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_APP_SETUP_FAILED,
            )
        return self.async_abort(reason=reason)

    async def _async_start_app(self) -> None:
        """Start the app and wait until it answers."""
        await get_app_manager(self.hass).async_schedule_start_addon()

        for _ in range(APP_START_ROUNDS):
            await asyncio.sleep(APP_START_INTERVAL)
            try:
                await self._async_connect_app()
            except (AddonError, *CLIENT_ERRORS) as err:
                _LOGGER.debug(
                    "App not ready yet, waiting %s seconds: %s",
                    APP_START_INTERVAL,
                    err,
                )
                continue
            return

        raise TimeoutError("Timeout waiting for the Voice app to start")

    async def _async_connect_app(self) -> None:
        """Find the app through its discovery info and ask what it is."""
        discovery_info = await get_app_manager(
            self.hass
        ).async_get_addon_discovery_info()
        self._host = discovery_info["host"]
        self._port = discovery_info["port"]
        self._info = await _async_get_info(self.hass, self._host, self._port)

    @override
    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle the app announcing itself through the Supervisor."""
        if not async_is_enabled(self.hass):
            return self.async_abort(reason="preview_feature_disabled")

        host: str = discovery_info.config["host"]
        port: int = discovery_info.config["port"]
        if await self._async_update_existing_entry(host, port):
            return self.async_abort(reason="already_configured")

        await self._async_handle_discovery_without_unique_id()

        try:
            self._info = await _async_get_info(self.hass, host, port)
        except CLIENT_ERRORS:
            return self.async_abort(reason="cannot_connect")
        except UnsupportedVersionError:
            return self.async_abort(reason="unsupported_version")

        self._host = host
        self._port = port
        return self._async_create_entry()

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle an app found on the network."""
        if not async_is_enabled(self.hass):
            return self.async_abort(reason="preview_feature_disabled")
        if discovery_info.port is None:
            return self.async_abort(reason="cannot_connect")

        host = discovery_info.host
        port = discovery_info.port
        if await self._async_update_existing_entry(host, port):
            return self.async_abort(reason="already_configured")

        await self._async_handle_discovery_without_unique_id()

        try:
            self._info = await _async_get_info(self.hass, host, port)
        except CLIENT_ERRORS:
            return self.async_abort(reason="cannot_connect")
        except UnsupportedVersionError:
            return self.async_abort(reason="unsupported_version")

        self._host = host
        self._port = port
        self.context["title_placeholders"] = {"name": self._info.name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the app found on the network."""
        if TYPE_CHECKING:
            assert self._info is not None
            assert self._host is not None

        if user_input is not None:
            return self._async_create_entry()

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._info.name, "host": self._host},
        )

    async def _async_update_existing_entry(self, host: str, port: int) -> bool:
        """Point the entry at a rediscovered app, and say whether there was one.

        A different host is left alone: the person may have pointed the entry
        at an app of their own.
        """
        for entry in self._async_current_entries(include_ignore=True):
            if entry.data.get(CONF_HOST) != host:
                return True
            updated = self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_PORT: port}
            )
            if entry.state is ConfigEntryState.SETUP_RETRY or (
                updated and entry.state is ConfigEntryState.LOADED
            ):
                # The app is back, or moved: a retry need not wait out its backoff
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return True
        return False

    @callback
    def _async_create_entry(self) -> ConfigFlowResult:
        """Create the entry, and clear any complaint from an earlier attempt.

        Another flow may have made one in the meantime, and there is one client.
        """
        if TYPE_CHECKING:
            assert self._info is not None
            assert self._host is not None
            assert self._port is not None
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_APP_SETUP_FAILED)
        data: dict[str, Any] = {CONF_HOST: self._host, CONF_PORT: self._port}
        if self._integration_created_app:
            data[CONF_INTEGRATION_CREATED_APP] = True
        return self.async_create_entry(title=self._info.name, data=data)
