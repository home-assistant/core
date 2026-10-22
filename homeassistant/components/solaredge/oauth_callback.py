"""SolarEdge's documented external_id echo carries HA's signed OAuth state."""

from dataclasses import dataclass
import time
from typing import TYPE_CHECKING

from aiohttp import web
from yarl import URL

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow
from homeassistant.helpers.config_entry_oauth2_flow import _decode_jwt
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

if TYPE_CHECKING:
    from .application_credentials import SolarEdgeAuthImplementation
    from .config_flow import SolarEdgeConfigFlow

CALLBACK_PATH = "/auth/external/callback/solaredge"
STATE_LIFETIME = 600
CALLBACK_VALIDATED = object()


@dataclass
class PendingAuthorization:
    """Bind a single consent attempt to its originating flow and implementation."""

    flow: SolarEdgeConfigFlow
    implementation: SolarEdgeAuthImplementation
    site_id: str
    redirect_uri: str
    expires: float


DATA_PENDING: HassKey[dict[str, PendingAuthorization]] = HassKey(
    "solaredge_oauth_pending"
)


@callback
def async_register_pending(
    hass: HomeAssistant, flow: SolarEdgeConfigFlow, url: str, site_id: str
) -> None:
    """Register only state generated for this native SolarEdge flow."""
    from .application_credentials import SolarEdgeAuthImplementation  # noqa: PLC0415

    assert isinstance(flow.flow_impl, SolarEdgeAuthImplementation)
    if DATA_PENDING not in hass.data:
        hass.data[DATA_PENDING] = {}
        hass.http.register_view(SolarEdgeOAuthCallbackView)
    pending = hass.data[DATA_PENDING]
    for key, value in list(pending.items()):
        if value.expires <= time.time() or value.flow is flow:
            del pending[key]
    query = URL(url).query
    pending[query["state"]] = PendingAuthorization(
        flow,
        flow.flow_impl,
        site_id,
        query["redirect_uri"],
        time.time() + STATE_LIFETIME,
    )


class SolarEdgeOAuthCallbackView(HomeAssistantView):
    """Accept external_id only for an outstanding, signed SolarEdge consent."""

    requires_auth = False
    url = CALLBACK_PATH
    name = "auth:external:callback:solaredge"

    async def get(self, request: web.Request) -> web.Response:
        """Validate and consume the state before resuming the native flow."""
        hass = request.app[KEY_HASS]
        query = request.query
        invalid = web.Response(text="Invalid SolarEdge OAuth callback", status=400)
        if any(
            len(query.getall(key, [])) > 1
            for key in ("state", "external_id", "code", "error")
        ):
            return invalid
        encoded = query.get("state") or query.get("external_id")
        if not encoded or (
            "state" in query
            and "external_id" in query
            and query["state"] != query["external_id"]
        ):
            return invalid
        state = _decode_jwt(hass, encoded)
        pending = hass.data.get(DATA_PENDING, {})
        attempt = pending.get(encoded)
        if state is None or attempt is None:
            return invalid
        flow = attempt.flow
        if (
            attempt.expires <= time.time()
            or state.get("flow_id") != flow.flow_id
            or state.get("redirect_uri") != attempt.redirect_uri
            or attempt.redirect_uri != attempt.implementation.redirect_uri
            or flow.DOMAIN != DOMAIN
            or flow.flow_impl is not attempt.implementation
            or flow.oauth_site_id != attempt.site_id
            or not flow.cur_step
            or flow.cur_step["type"] is not FlowResultType.EXTERNAL_STEP
            or flow.cur_step["step_id"] != "auth"
        ):
            return invalid
        try:
            active = hass.config_entries.flow.async_get(flow.flow_id)
        except UnknownFlow:
            return invalid
        if active["handler"] != DOMAIN or active["step_id"] != "auth":
            return invalid
        if bool(query.get("code")) == bool(query.get("error")):
            return invalid
        # No await before consumption: concurrent/replayed callbacks cannot resume twice.
        del pending[encoded]
        user_input = {"state": state, "solaredge_callback": CALLBACK_VALIDATED}
        if "code" in query:
            user_input["code"] = query["code"]
        else:
            user_input["error"] = "access_denied"
        try:
            await hass.config_entries.flow.async_configure(flow.flow_id, user_input)
        except UnknownFlow:
            return invalid
        return web.Response(
            content_type="text/html",
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
            text=(
                "<!doctype html><title>SolarEdge authorization</title>"
                "<p>Authorization response received. Return to Home Assistant to "
                "finish setup. You can close this tab if it did not close automatically.</p>"
                "<script>window.close()</script>"
            ),
        )
