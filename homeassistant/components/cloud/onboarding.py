"""Cloud onboarding views."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import TYPE_CHECKING, Any, Concatenate

from aiohttp import web
from aiohttp.web_exceptions import HTTPUnauthorized

from homeassistant.components.http import KEY_HASS
from homeassistant.components.onboarding import (
    BaseOnboardingView,
    NoAuthBaseOnboardingView,
)
from homeassistant.core import HomeAssistant

from . import http_api as cloud_http
from .const import DATA_CLOUD

if TYPE_CHECKING:
    from homeassistant.components.onboarding import OnboardingStoreData


async def async_setup_views(hass: HomeAssistant, data: OnboardingStoreData) -> None:
    """Set up the cloud views."""

    hass.http.register_view(CloudForgotPasswordView(data))
    hass.http.register_view(CloudLoginView(data))
    hass.http.register_view(CloudLogoutView(data))
    hass.http.register_view(CloudStatusView(data))


def ensure_not_done[_ViewT: BaseOnboardingView, **_P](
    func: Callable[
        Concatenate[_ViewT, web.Request, _P],
        Coroutine[Any, Any, web.Response],
    ],
) -> Callable[Concatenate[_ViewT, web.Request, _P], Coroutine[Any, Any, web.Response]]:
    """Home Assistant API decorator to check onboarding and cloud."""

    @wraps(func)
    async def _ensure_not_done(
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

        return await func(self, request, *args, **kwargs)

    return _ensure_not_done


class CloudForgotPasswordView(
    NoAuthBaseOnboardingView, cloud_http.CloudForgotPasswordView
):
    """View to start Forgot Password flow."""

    url = "/api/onboarding/cloud/forgot_password"
    name = "api:onboarding:cloud:forgot_password"

    @ensure_not_done
    async def post(self, request: web.Request) -> web.Response:
        """Handle forgot password request."""
        return await super()._post(request)


class CloudLoginView(NoAuthBaseOnboardingView, cloud_http.CloudLoginView):
    """Login to Home Assistant Cloud."""

    url = "/api/onboarding/cloud/login"
    name = "api:onboarding:cloud:login"

    @ensure_not_done
    async def post(self, request: web.Request) -> web.Response:
        """Handle login request."""
        return await super()._post(request)


class CloudLogoutView(NoAuthBaseOnboardingView, cloud_http.CloudLogoutView):
    """Log out of the Home Assistant cloud."""

    url = "/api/onboarding/cloud/logout"
    name = "api:onboarding:cloud:logout"

    @ensure_not_done
    async def post(self, request: web.Request) -> web.Response:
        """Handle logout request."""
        return await super()._post(request)


class CloudStatusView(NoAuthBaseOnboardingView):
    """Get cloud status view."""

    url = "/api/onboarding/cloud/status"
    name = "api:onboarding:cloud:status"

    @ensure_not_done
    async def get(self, request: web.Request) -> web.Response:
        """Return cloud status."""
        hass = request.app[KEY_HASS]
        cloud = hass.data[DATA_CLOUD]
        return self.json({"logged_in": cloud.is_logged_in})
