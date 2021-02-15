"""Onboarding views."""
import asyncio

import voluptuous as vol

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.auth import indieauth
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import HTTP_BAD_REQUEST, HTTP_FORBIDDEN
from homeassistant.core import callback

from .const import (
    DEFAULT_AREAS,
    DOMAIN,
    STEP_CORE_CONFIG,
    STEP_INTEGRATION,
    STEP_MOB_INTEGRATION,
    STEP_USER,
    STEPS,
)


async def async_setup(hass, data, store):
    """Set up the onboarding view."""
    hass.http.register_view(OnboardingView(data, store))
    hass.http.register_view(UserOnboardingView(data, store))
    hass.http.register_view(CoreConfigOnboardingView(data, store))
    hass.http.register_view(IntegrationOnboardingView(data, store))
    hass.http.register_view(MobIntegrationOnboardingView(data, store))


class OnboardingView(HomeAssistantView):
    """Return the onboarding status."""

    requires_auth = False
    url = "/api/onboarding"
    name = "api:onboarding"

    def __init__(self, data, store):
        """Initialize the onboarding view."""
        self._store = store
        self._data = data

    async def get(self, request):
        """Return the onboarding status."""
        return self.json(
            [{"step": key, "done": key in self._data["done"]} for key in STEPS]
        )


class _BaseOnboardingView(HomeAssistantView):
    """Base class for onboarding."""

    step = None

    def __init__(self, data, store):
        """Initialize the onboarding view."""
        self._store = store
        self._data = data
        self._lock = asyncio.Lock()

    @callback
    def _async_is_done(self):
        """Return if this step is done."""
        return self.step in self._data["done"]

    async def _async_mark_done(self, hass):
        """Mark step as done."""
        self._data["done"].append(self.step)
        await self._store.async_save(self._data)

        if set(self._data["done"]) == set(STEPS):
            hass.data[DOMAIN] = True


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
    async def post(self, request, data):
        """Handle user creation, area creation."""
        hass = request.app["hass"]

        async with self._lock:
            if self._async_is_done():
                return self.json_message("User step already done", HTTP_FORBIDDEN)

            provider = _async_get_hass_provider(hass)
            await provider.async_initialize()

            user = await hass.auth.async_create_user(data["name"], [GROUP_ID_ADMIN])
            await hass.async_add_executor_job(
                provider.data.add_auth, data["username"], data["password"]
            )
            credentials = await provider.async_get_or_create_credentials(
                {"username": data["username"]}
            )
            await provider.data.async_save()
            await hass.auth.async_link_user(user, credentials)
            if "person" in hass.config.components:
                await hass.components.person.async_create_person(
                    data["name"], user_id=user.id
                )

            # Create default areas using the users supplied language.
            translations = await hass.helpers.translation.async_get_translations(
                data["language"], "area", DOMAIN
            )

            area_registry = await hass.helpers.area_registry.async_get_registry()

            for area in DEFAULT_AREAS:
                area_registry.async_create(
                    translations[f"component.onboarding.area.{area}"]
                )

            await self._async_mark_done(hass)

            # Return authorization code for fetching tokens and connect
            # during onboarding.
            auth_code = hass.components.auth.create_auth_code(data["client_id"], user)
            return self.json({"auth_code": auth_code})


class CoreConfigOnboardingView(_BaseOnboardingView):
    """View to finish core config onboarding step."""

    url = "/api/onboarding/core_config"
    name = "api:onboarding:core_config"
    step = STEP_CORE_CONFIG

    async def post(self, request):
        """Handle finishing core config step."""
        hass = request.app["hass"]

        async with self._lock:
            if self._async_is_done():
                return self.json_message(
                    "Core config step already done", HTTP_FORBIDDEN
                )

            await self._async_mark_done(hass)

            await hass.config_entries.flow.async_init(
                "met", context={"source": "onboarding"}
            )

            if (
                hass.components.hassio.is_hassio()
                and "raspberrypi" in hass.components.hassio.get_core_info()["machine"]
            ):
                await hass.config_entries.flow.async_init(
                    "rpi_power", context={"source": "onboarding"}
                )

            return self.json({})


class MobIntegrationOnboardingView(_BaseOnboardingView):
    """View to finish mob integration onboarding step."""

    url = "/api/onboarding/mob_integration"
    name = "api:onboarding:mob_integration"
    step = STEP_MOB_INTEGRATION

    async def post(self, request):
        """Handle finishing core config step."""
        hass = request.app["hass"]

        async with self._lock:
            if self._async_is_done():
                return self.json_message(
                    "Core config step already done", HTTP_FORBIDDEN
                )

            await self._async_mark_done(hass)

            await hass.config_entries.flow.async_init(
                "met", context={"source": "onboarding"}
            )

            return self.json({})


class IntegrationOnboardingView(_BaseOnboardingView):
    """View to finish integration onboarding step."""

    url = "/api/onboarding/integration"
    name = "api:onboarding:integration"
    step = STEP_INTEGRATION

    @RequestDataValidator(
        vol.Schema({vol.Required("client_id"): str, vol.Required("redirect_uri"): str})
    )
    async def post(self, request, data):
        """Handle token creation."""
        hass = request.app["hass"]
        user = request["hass_user"]

        async with self._lock:
            if self._async_is_done():
                return self.json_message(
                    "Integration step already done", HTTP_FORBIDDEN
                )

            await self._async_mark_done(hass)

            # Validate client ID and redirect uri
            if not await indieauth.verify_redirect_uri(
                request.app["hass"], data["client_id"], data["redirect_uri"]
            ):
                return self.json_message(
                    "invalid client id or redirect uri", HTTP_BAD_REQUEST
                )

            # Return authorization code so we can redirect user and log them in
            auth_code = hass.components.auth.create_auth_code(data["client_id"], user)
            return self.json({"auth_code": auth_code})


@callback
def _async_get_hass_provider(hass):
    """Get the Home Assistant auth provider."""
    for prv in hass.auth.auth_providers:
        if prv.type == "homeassistant":
            return prv

    raise RuntimeError("No Home Assistant provider found")
