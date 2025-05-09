"""Onboarding views."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from functools import wraps
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Concatenate, cast

from aiohttp import web
from aiohttp.web_exceptions import HTTPUnauthorized
import voluptuous as vol

from homeassistant import msh_utils
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.auth.providers.homeassistant import HassAuthProvider
from homeassistant.components import person
from homeassistant.components.auth import indieauth
from homeassistant.components.backup import (
    BackupManager,
    Folder,
    IncorrectPasswordError,
    http as backup_http,
)
from homeassistant.components.http import KEY_HASS, KEY_HASS_REFRESH_TOKEN_ID
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.backup import async_get_manager as async_get_backup_manager
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component

if TYPE_CHECKING:
    from . import OnboardingData, OnboardingStorage, OnboardingStoreData

from .const import (
    DEFAULT_AREAS,
    DOMAIN,
    STEP_ANALYTICS,
    STEP_CORE_CONFIG,
    STEP_INTEGRATION,
    STEP_USER,
    STEPS,
)


async def async_setup(
    hass: HomeAssistant, data: OnboardingStoreData, store: OnboardingStorage
) -> None:
    """Set up the onboarding view."""
    hass.http.register_view(OnboardingView(data, store))
    hass.http.register_view(InstallationTypeOnboardingView(data))
    hass.http.register_view(UserOnboardingView(data, store))
    hass.http.register_view(CoreConfigOnboardingView(data, store))
    hass.http.register_view(IntegrationOnboardingView(data, store))
    hass.http.register_view(AnalyticsOnboardingView(data, store))
    hass.http.register_view(BackupInfoView(data))
    hass.http.register_view(RestoreBackupView(data))
    hass.http.register_view(UploadBackupView(data))

class OnboardingView(HomeAssistantView):
    """Return the onboarding status."""

    requires_auth = False
    url = "/api/onboarding"
    name = "api:onboarding"

    def __init__(self, data: OnboardingStoreData, store: OnboardingStorage) -> None:
        """Initialize the onboarding view."""
        self._store = store
        self._data = data

    async def get(self, request: web.Request) -> web.Response:
        """Return the onboarding status."""
        return self.json(
            [{"step": key, "done": key in self._data["done"]} for key in STEPS]
        )


class InstallationTypeOnboardingView(HomeAssistantView):
    """Return the installation type during onboarding."""

    requires_auth = False
    url = "/api/onboarding/installation_type"
    name = "api:onboarding:installation_type"

    def __init__(self, data: OnboardingStoreData) -> None:
        """Initialize the onboarding installation type view."""
        self._data = data

    async def get(self, request: web.Request) -> web.Response:
        """Return the onboarding status."""
        if self._data["done"]:
            raise HTTPUnauthorized

        hass = request.app[KEY_HASS]
        info = await async_get_system_info(hass)
        return self.json({"installation_type": info["installation_type"]})


class _BaseOnboardingView(HomeAssistantView):
    """Base class for onboarding."""

    step: str

    def __init__(self, data: OnboardingStoreData, store: OnboardingStorage) -> None:
        """Initialize the onboarding view."""
        self._store = store
        self._data = data
        self._lock = asyncio.Lock()

    @callback
    def _async_is_done(self) -> bool:
        """Return if this step is done."""
        return self.step in self._data["done"]

    async def _async_mark_done(self, hass: HomeAssistant) -> None:
        """Mark step as done."""
        self._data["done"].append(self.step)
        await self._store.async_save(self._data)

        if set(self._data["done"]) == set(STEPS):
            data: OnboardingData = hass.data[DOMAIN]
            data.onboarded = True
            for listener in data.listeners:
                listener()


class UserOnboardingView(_BaseOnboardingView):
    """View to handle create user onboarding step."""

    url = "/api/onboarding/users"
    name = "api:onboarding:users"
    requires_auth = False
    step = STEP_USER

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("name"): str,
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Required("secret_key"): str,
                vol.Required("home_name"): str,
                vol.Required("client_id"): str,
                vol.Required("language"): str,
            }
        )
    )
    async def post(self, request: web.Request, data: dict[str, str]) -> web.Response:
        """Handle user creation, area creation."""
        hass = request.app[KEY_HASS]

        async with self._lock:
            if self._async_is_done():
                return self.json_message("User step already done", HTTPStatus.FORBIDDEN)

            scheme = request.scheme
            host = request.host
            host_url = f"{scheme}://{host}"

            # Intercept to verify secret key
            verification_result = await msh_utils.verify_secret_key(
                data["secret_key"],
                data["home_name"],
                data["name"],
                data["username"],
                data["password"],
                host_url,
            )

            if not verification_result["success"]:
                return self.json_message(
                    verification_result["message"],
                    HTTPStatus.BAD_REQUEST,
                )

            # Extract serverId if needed from the cloud function's response
            server_id = verification_result["data"].get("serverId")
            await msh_utils.write_key_value_to_config_file(
                msh_utils.SERVER_ID, server_id
            )

            # extract external url
            external_url = verification_result["data"].get("externalUrl")
            await msh_utils.write_key_value_to_config_file(
                msh_utils.EXTERNAL_URL, external_url
            )

            # save the code
            await msh_utils.fetch_and_save_device_limit(data["username"], server_id)

            # config_path = os.path.join(hass.config.config_dir, YAML_CONFIG_FILE)
            # await msh_utils.add_external_url_into_confi_cors(external_url, config_path)

            provider = _async_get_hass_provider(hass)
            await provider.async_initialize()

            user = await hass.auth.async_create_user(
                data["name"], group_ids=[GROUP_ID_ADMIN]
            )
            await provider.async_add_auth(data["username"], data["password"])
            credentials = await provider.async_get_or_create_credentials(
                {"username": data["username"]}
            )
            await hass.auth.async_link_user(user, credentials)
            if "person" in hass.config.components:
                await person.async_create_person(hass, data["name"], user_id=user.id)

            # Create default areas using the users supplied language.
            translations = await async_get_translations(
                hass, data["language"], "area", {DOMAIN}
            )

            area_registry = ar.async_get(hass)

            for area in DEFAULT_AREAS:
                name = translations.get(
                    f"component.onboarding.area.{area}", "Living Room"
                )
                # Guard because area might have been created by an automatically
                # set up integration.
                if not area_registry.async_get_area_by_name(name):
                    area_registry.async_create(name)

            await self._async_mark_done(hass)

            # Return authorization code for fetching tokens and connect
            # during onboarding.
            # pylint: disable-next=import-outside-toplevel
            from homeassistant.components.auth import create_auth_code

            auth_code = create_auth_code(hass, data["client_id"], credentials)
            return self.json({"auth_code": auth_code})


class CoreConfigOnboardingView(_BaseOnboardingView):
    """View to finish core config onboarding step."""

    url = "/api/onboarding/core_config"
    name = "api:onboarding:core_config"
    step = STEP_CORE_CONFIG

    async def post(self, request: web.Request) -> web.Response:
        """Handle finishing core config step."""
        hass = request.app[KEY_HASS]

        async with self._lock:
            if self._async_is_done():
                return self.json_message(
                    "Core config step already done", HTTPStatus.FORBIDDEN
                )

            await self._async_mark_done(hass)

            # Integrations to set up when finishing onboarding
            onboard_integrations = [
                "google_translate",
                "met",
                "radio_browser",
                "shopping_list",
            ]

            for domain in onboard_integrations:
                # Create tasks so onboarding isn't affected
                # by errors in these integrations.
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        domain, context={"source": "onboarding"}
                    ),
                    f"onboarding_setup_{domain}",
                )

            if "analytics" not in hass.config.components:
                # If by some chance that analytics has not finished
                # setting up, wait for it here so its ready for the
                # next step.
                await async_setup_component(hass, "analytics", {})

            return self.json({})


class IntegrationOnboardingView(_BaseOnboardingView):
    """View to finish integration onboarding step."""

    url = "/api/onboarding/integration"
    name = "api:onboarding:integration"
    step = STEP_INTEGRATION

    @RequestDataValidator(
        vol.Schema({vol.Required("client_id"): str, vol.Required("redirect_uri"): str})
    )
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Handle token creation."""
        hass = request.app[KEY_HASS]
        refresh_token_id = request[KEY_HASS_REFRESH_TOKEN_ID]

        async with self._lock:
            if self._async_is_done():
                return self.json_message(
                    "Integration step already done", HTTPStatus.FORBIDDEN
                )

            await self._async_mark_done(hass)

            # Validate client ID and redirect uri
            if not await indieauth.verify_redirect_uri(
                request.app[KEY_HASS], data["client_id"], data["redirect_uri"]
            ):
                return self.json_message(
                    "invalid client id or redirect uri", HTTPStatus.BAD_REQUEST
                )

            refresh_token = hass.auth.async_get_refresh_token(refresh_token_id)
            if refresh_token is None or refresh_token.credential is None:
                return self.json_message(
                    "Credentials for user not available", HTTPStatus.FORBIDDEN
                )

            # Return authorization code so we can redirect user and log them in
            # pylint: disable-next=import-outside-toplevel
            from homeassistant.components.auth import create_auth_code

            auth_code = create_auth_code(
                hass, data["client_id"], refresh_token.credential
            )
            return self.json({"auth_code": auth_code})


class AnalyticsOnboardingView(_BaseOnboardingView):
    """View to finish analytics onboarding step."""

    url = "/api/onboarding/analytics"
    name = "api:onboarding:analytics"
    step = STEP_ANALYTICS

    async def post(self, request: web.Request) -> web.Response:
        """Handle finishing analytics step."""
        hass = request.app[KEY_HASS]

        async with self._lock:
            if self._async_is_done():
                return self.json_message(
                    "Analytics config step already done", HTTPStatus.FORBIDDEN
                )

            await self._async_mark_done(hass)

            return self.json({})


class BackupOnboardingView(HomeAssistantView):
    """Backup onboarding view."""

    requires_auth = False

    def __init__(self, data: OnboardingStoreData) -> None:
        """Initialize the view."""
        self._data = data


def with_backup_manager[_ViewT: BackupOnboardingView, **_P](
    func: Callable[
        Concatenate[_ViewT, BackupManager, web.Request, _P],
        Coroutine[Any, Any, web.Response],
    ],
) -> Callable[Concatenate[_ViewT, web.Request, _P], Coroutine[Any, Any, web.Response]]:
    """Home Assistant API decorator to check onboarding and inject manager."""

    @wraps(func)
    async def with_backup(
        self: _ViewT,
        request: web.Request,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> web.Response:
        """Check admin and call function."""
        if self._data["done"]:
            raise HTTPUnauthorized

        try:
            manager = await async_get_backup_manager(request.app[KEY_HASS])
        except HomeAssistantError:
            return self.json(
                {"code": "backup_disabled"},
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        return await func(self, manager, request, *args, **kwargs)

    return with_backup


class BackupInfoView(BackupOnboardingView):
    """Get backup info view."""

    url = "/api/onboarding/backup/info"
    name = "api:onboarding:backup:info"

    @with_backup_manager
    async def get(self, manager: BackupManager, request: web.Request) -> web.Response:
        """Return backup info."""
        backups, _ = await manager.async_get_backups()
        return self.json(
            {
                "backups": list(backups.values()),
                "state": manager.state,
                "last_non_idle_event": manager.last_non_idle_event,
            }
        )


class RestoreBackupView(BackupOnboardingView):
    """Restore backup view."""

    url = "/api/onboarding/backup/restore"
    name = "api:onboarding:backup:restore"

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("backup_id"): str,
                vol.Required("agent_id"): str,
                vol.Optional("password"): str,
                vol.Optional("restore_addons"): [str],
                vol.Optional("restore_database", default=True): bool,
                vol.Optional("restore_folders"): [vol.Coerce(Folder)],
            }
        )
    )
    @with_backup_manager
    async def post(
        self, manager: BackupManager, request: web.Request, data: dict[str, Any]
    ) -> web.Response:
        """Restore a backup."""
        try:
            await manager.async_restore_backup(
                data["backup_id"],
                agent_id=data["agent_id"],
                password=data.get("password"),
                restore_addons=data.get("restore_addons"),
                restore_database=data["restore_database"],
                restore_folders=data.get("restore_folders"),
                restore_homeassistant=True,
            )
        except IncorrectPasswordError:
            return self.json(
                {"code": "incorrect_password"}, status_code=HTTPStatus.BAD_REQUEST
            )
        except HomeAssistantError as err:
            return self.json(
                {"code": "restore_failed", "message": str(err)},
                status_code=HTTPStatus.BAD_REQUEST,
            )
        return web.Response(status=HTTPStatus.OK)


class UploadBackupView(BackupOnboardingView, backup_http.UploadBackupView):
    """Upload backup view."""

    url = "/api/onboarding/backup/upload"
    name = "api:onboarding:backup:upload"

    @with_backup_manager
    async def post(self, manager: BackupManager, request: web.Request) -> web.Response:
        """Upload a backup file."""
        return await self._post(request)


@callback
def _async_get_hass_provider(hass: HomeAssistant) -> HassAuthProvider:
    """Get the Home Assistant auth provider."""
    for prv in hass.auth.auth_providers:
        if prv.type == "homeassistant":
            return cast(HassAuthProvider, prv)

    raise RuntimeError("No Home Assistant provider found")
