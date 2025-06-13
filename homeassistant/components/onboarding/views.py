"""Onboarding views."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, Any, Protocol, cast

from aiohttp import web
from aiohttp.web_exceptions import HTTPUnauthorized
import voluptuous as vol

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.auth.providers.homeassistant import HassAuthProvider
from homeassistant.components import person
from homeassistant.components.auth import indieauth
from homeassistant.components.http import KEY_HASS, KEY_HASS_REFRESH_TOKEN_ID
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, integration_platform
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component, async_wait_component

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

_LOGGER = logging.getLogger(__name__)


async def async_setup(
    hass: HomeAssistant, data: OnboardingStoreData, store: OnboardingStorage
) -> None:
    """Set up the onboarding view."""
    await async_process_onboarding_platforms(hass)
    hass.http.register_view(OnboardingStatusView(data, store))
    hass.http.register_view(InstallationTypeOnboardingView(data))
    hass.http.register_view(UserOnboardingView(data, store))
    hass.http.register_view(CoreConfigOnboardingView(data, store))
    hass.http.register_view(IntegrationOnboardingView(data, store))
    hass.http.register_view(AnalyticsOnboardingView(data, store))
    hass.http.register_view(WaitIntegrationOnboardingView(data))


class OnboardingPlatformProtocol(Protocol):
    """Define the format of onboarding platforms."""

    async def async_setup_views(
        self, hass: HomeAssistant, data: OnboardingStoreData
    ) -> None:
        """Set up onboarding views."""


async def async_process_onboarding_platforms(hass: HomeAssistant) -> None:
    """Start processing onboarding platforms."""
    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_onboarding_platform, wait_for_platforms=False
    )


async def _register_onboarding_platform(
    hass: HomeAssistant, integration_domain: str, platform: OnboardingPlatformProtocol
) -> None:
    """Register a onboarding platform."""
    if not hasattr(platform, "async_setup_views"):
        _LOGGER.debug(
            "'%s.onboarding' is not a valid onboarding platform",
            integration_domain,
        )
        return
    await platform.async_setup_views(hass, hass.data[DOMAIN].steps)


class BaseOnboardingView(HomeAssistantView):
    """Base class for onboarding views."""

    def __init__(self, data: OnboardingStoreData) -> None:
        """Initialize the onboarding view."""
        self._data = data


class NoAuthBaseOnboardingView(BaseOnboardingView):
    """Base class for unauthenticated onboarding views."""

    requires_auth = False


class OnboardingStatusView(NoAuthBaseOnboardingView):
    """Return the onboarding status."""

    url = "/api/onboarding"
    name = "api:onboarding"

    def __init__(self, data: OnboardingStoreData, store: OnboardingStorage) -> None:
        """Initialize the onboarding view."""
        super().__init__(data)
        self._store = store

    async def get(self, request: web.Request) -> web.Response:
        """Return the onboarding status."""
        return self.json(
            [{"step": key, "done": key in self._data["done"]} for key in STEPS]
        )


class InstallationTypeOnboardingView(NoAuthBaseOnboardingView):
    """Return the installation type during onboarding."""

    url = "/api/onboarding/installation_type"
    name = "api:onboarding:installation_type"

    async def get(self, request: web.Request) -> web.Response:
        """Return the onboarding status."""
        if self._data["done"]:
            raise HTTPUnauthorized

        hass = request.app[KEY_HASS]
        info = await async_get_system_info(hass)
        return self.json({"installation_type": info["installation_type"]})


class _BaseOnboardingStepView(BaseOnboardingView):
    """Base class for an onboarding step."""

    step: str

    def __init__(self, data: OnboardingStoreData, store: OnboardingStorage) -> None:
        """Initialize the onboarding view."""
        super().__init__(data)
        self._store = store
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


class UserOnboardingView(_BaseOnboardingStepView):
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
            if await async_wait_component(hass, "person"):
                await person.async_create_person(hass, data["name"], user_id=user.id)

            # Create default areas using the users supplied language.
            translations = await async_get_translations(
                hass, data["language"], "area", {DOMAIN}
            )

            area_registry = ar.async_get(hass)

            for area in DEFAULT_AREAS:
                name = translations[f"component.onboarding.area.{area}"]
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


class CoreConfigOnboardingView(_BaseOnboardingStepView):
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


class IntegrationOnboardingView(_BaseOnboardingStepView):
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


class WaitIntegrationOnboardingView(NoAuthBaseOnboardingView):
    """Get backup info view."""

    url = "/api/onboarding/integration/wait"
    name = "api:onboarding:integration:wait"

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("domain"): str,
            }
        )
    )
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Handle wait for integration command."""
        hass = request.app[KEY_HASS]
        domain = data["domain"]
        return self.json(
            {
                "integration_loaded": await async_wait_component(hass, domain),
            }
        )


class AnalyticsOnboardingView(_BaseOnboardingStepView):
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


@callback
def _async_get_hass_provider(hass: HomeAssistant) -> HassAuthProvider:
    """Get the Home Assistant auth provider."""
    for prv in hass.auth.auth_providers:
        if prv.type == "homeassistant":
            return cast(HassAuthProvider, prv)

    raise RuntimeError("No Home Assistant provider found")
