"""Cloud onboarding views."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Concatenate

from aiohttp import web
from aiohttp.web_exceptions import HTTPUnauthorized

from homeassistant.components.http import KEY_HASS
from homeassistant.components.onboarding import (
    _BaseOnboardingView,
    _NoAuthBaseOnboardingView,
)
from homeassistant.core import HomeAssistant

from . import http_api as cloud_http
from .const import DATA_CLOUD

if TYPE_CHECKING:
    from homeassistant.components.onboarding import OnboardingStoreData


async def async_setup_views(hass: HomeAssistant, data: OnboardingStoreData) -> None:
    """Set up the cloud views."""

    def with_cloud[_ViewT: _BaseOnboardingView, **_P](
        func: Callable[
            Concatenate[_ViewT, web.Request, _P],
            Coroutine[Any, Any, web.Response],
        ],
    ) -> Callable[
        Concatenate[_ViewT, web.Request, _P], Coroutine[Any, Any, web.Response]
    ]:
        """Home Assistant API decorator to check onboarding and cloud."""

        @wraps(func)
        async def _with_cloud(
            self: _ViewT,
            request: web.Request,
            *args: _P.args,
            **kwargs: _P.kwargs,
        ) -> web.Response:
            """Check onboarding status, cloud and call function."""
            if self._data["done"]:
                # If at least one onboarding step is done, we don't allow accessing
                # the cloud onboarding views.
                raise HTTPUnauthorized

            hass = request.app[KEY_HASS]
            if DATA_CLOUD not in hass.data:
                return self.json(
                    {"code": "cloud_disabled"},
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                )

            return await func(self, request, *args, **kwargs)

        return _with_cloud

    class CloudForgotPasswordView(
        _NoAuthBaseOnboardingView, cloud_http.CloudForgotPasswordView
    ):
        """View to start Forgot Password flow."""

        url = "/api/onboarding/cloud/forgot_password"
        name = "api:onboarding:cloud:forgot_password"

        @with_cloud
        async def post(self, request: web.Request) -> web.Response:
            """Handle forgot password request."""
            return await super()._post(request)

    class CloudLoginView(_NoAuthBaseOnboardingView, cloud_http.CloudLoginView):
        """Login to Home Assistant Cloud."""

        url = "/api/onboarding/cloud/login"
        name = "api:onboarding:cloud:login"

        @with_cloud
        async def post(self, request: web.Request) -> web.Response:
            """Handle login request."""
            return await super()._post(request)

    class CloudLogoutView(_NoAuthBaseOnboardingView, cloud_http.CloudLogoutView):
        """Log out of the Home Assistant cloud."""

        url = "/api/onboarding/cloud/logout"
        name = "api:onboarding:cloud:logout"

        @with_cloud
        async def post(self, request: web.Request) -> web.Response:
            """Handle logout request."""
            return await super()._post(request)

    class CloudStatusView(_NoAuthBaseOnboardingView):
        """Get cloud status view."""

        url = "/api/onboarding/cloud/status"
        name = "api:onboarding:cloud:status"

        @with_cloud
        async def get(self, request: web.Request) -> web.Response:
            """Return cloud status."""
            hass = request.app[KEY_HASS]
            cloud = hass.data[DATA_CLOUD]
            return self.json({"logged_in": cloud.is_logged_in})

    hass.http.register_view(CloudForgotPasswordView(data))
    hass.http.register_view(CloudLoginView(data))
    hass.http.register_view(CloudLogoutView(data))
    hass.http.register_view(CloudStatusView(data))
