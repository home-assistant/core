"""Onboarding views."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, cast

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
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component
from homeassistant.util.async_ import create_eager_task

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
            if "person" in hass.config.components:
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

            # pylint: disable-next=import-outside-toplevel
            from homeassistant.components import hassio

            if (
                hassio.is_hassio(hass)
                and (core_info := hassio.get_core_info(hass))
                and "raspberrypi" in core_info["machine"]
            ):
                onboard_integrations.append("rpi_power")

            coros: list[Coroutine[Any, Any, Any]] = [
                hass.config_entries.flow.async_init(
                    domain, context={"source": "onboarding"}
                )
                for domain in onboard_integrations
            ]

            if "analytics" not in hass.config.components:
                # If by some chance that analytics has not finished
                # setting up, wait for it here so its ready for the
                # next step.
                coros.append(async_setup_component(hass, "analytics", {}))

            # Set up integrations after onboarding and ensure
            # analytics is ready for the next step.
            await asyncio.gather(*(create_eager_task(coro) for coro in coros))

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


@callback
def _async_get_hass_provider(hass: HomeAssistant) -> HassAuthProvider:
    """Get the Home Assistant auth provider."""
    for prv in hass.auth.auth_providers:
        if prv.type == "homeassistant":
            return cast(HassAuthProvider, prv)

    raise RuntimeError("No Home Assistant provider found")
