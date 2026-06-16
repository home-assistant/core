"""Config flow for the A Better Routeplanner integration."""

import base64
from collections.abc import Mapping
import json
import logging
from typing import Any, cast

from aioabrp import AbrpApiError, AbrpAuthError, AbrpClient, AbrpVehicle, StaticAuth
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import ABRP_APP_KEY, CONF_VEHICLE_IDS, DOMAIN
from .oauth import AbetterrouteplannerOAuth2Implementation


class AbetterrouteplannerFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle A Better Routeplanner OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    _oauth_data: dict[str, Any]
    _vehicles: list[AbrpVehicle]
    _payload: dict[str, Any]

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Prefill the ABRP login form via ``login_hint`` on reauth.

        On reauth we know which email previously authorized this entry
        (carried in the id_token), so we hand it back to the IdP via
        ``login_hint`` so the login form pre-fills. Falls through to the
        default empty dict for any flow without a usable id_token, so a
        legacy entry, a malformed token, or a missing claim degrades to
        "no prefill" rather than blocking reauth.
        """
        if self.source != SOURCE_REAUTH:
            return {}
        token = self._get_reauth_entry().data.get("token", {})
        id_token = token.get("id_token")
        if not id_token:
            return {}
        try:
            payload = _decode_jwt_payload(id_token)
            email = payload["email"]
        except ValueError, IndexError, KeyError, TypeError:
            return {}
        if not isinstance(email, str) or not email:
            return {}
        return {"login_hint": email}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user.

        The integration ships a built-in public OIDC client (no Application
        Credentials platform), so the implementation must be registered on
        demand here — ``async_setup`` only runs once a config entry exists.
        """
        if not await config_entry_oauth2_flow.async_get_implementations(
            self.hass, DOMAIN
        ):
            config_entry_oauth2_flow.async_register_implementation(
                self.hass, DOMAIN, AbetterrouteplannerOAuth2Implementation(self.hass)
            )
        return await super().async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a successful OAuth2 authorization.

        On the initial-add path: fetch the user's garage, stash it, and hand
        off to ``async_step_pick_vehicles`` so the user can pick which
        vehicles to track.

        On the reauth path: no picker; the existing selection is sticky and
        we just refresh the stored token. ``data_updates=data`` is used so
        the existing ``vehicle_ids`` are preserved across the reauth.
        """
        # The IdP issues id_token via the authorization_code grant used by
        # both initial-add and reauth (the scope is ``oidc``). A missing
        # id_token here means the IdP misbehaved; abort safely rather than
        # silently accept a token that we can't bind to a verified account.
        id_token = data["token"].get("id_token")
        if id_token is None:
            return self.async_abort(reason="oauth_error")
        try:
            payload = _decode_jwt_payload(id_token)
            sub = str(payload["sub"])
        except ValueError, IndexError, KeyError, TypeError:
            return self.async_abort(reason="oauth_error")
        self._payload = payload
        await self.async_set_unique_id(sub)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )

        self._abort_if_unique_id_configured()

        client = AbrpClient(
            async_get_clientsession(self.hass),
            ABRP_APP_KEY,
            StaticAuth(data["token"]["access_token"]),
        )
        try:
            vehicles = await client.async_get_vehicles()
        except AbrpAuthError:
            return self.async_abort(reason="api_unauthorized")
        except AbrpApiError:
            return self.async_abort(reason="cannot_connect")

        if not vehicles:
            return self.async_abort(reason="no_vehicles")

        self._oauth_data = data
        self._vehicles = vehicles
        return await self.async_step_pick_vehicles()

    async def async_step_pick_vehicles(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user which of their ABRP vehicles to track in Home Assistant."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_VEHICLE_IDS]:
                # Re-check unique_id at submission time so a parallel flow
                # that completed between OAuth and picker doesn't race past
                # the earlier ``_abort_if_unique_id_configured`` call.
                self._abort_if_unique_id_configured()
                # Bypass ``super().async_oauth_create_entry`` and call
                # ``async_create_entry`` directly so the ``vehicle_ids`` key we
                # add to ``data`` doesn't rely on the base class forwarding
                # unknown keys verbatim.
                display_name = _display_name_from_claims(self._payload)
                title = (
                    f"{self.flow_impl.name} ({display_name})"
                    if display_name
                    else self.flow_impl.name
                )
                return self.async_create_entry(
                    title=title,
                    data={
                        **self._oauth_data,
                        CONF_VEHICLE_IDS: user_input[CONF_VEHICLE_IDS],
                    },
                )
            errors["base"] = "select_at_least_one"

        options = [
            SelectOptionDict(
                value=str(vehicle.vehicle_id),
                label=vehicle.name or vehicle.vehicle_model,
            )
            for vehicle in self._vehicles
        ]
        # On first render: suggest selecting all vehicles. On error-driven
        # re-render: preserve the user's last selection so the rejected
        # submission isn't silently overwritten with the default set.
        if user_input is None:
            suggested: list[str] = [str(v.vehicle_id) for v in self._vehicles]
        else:
            suggested = user_input[CONF_VEHICLE_IDS]
        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_VEHICLE_IDS): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            {CONF_VEHICLE_IDS: suggested},
        )
        return self.async_show_form(
            step_id="pick_vehicles", data_schema=schema, errors=errors
        )


def _decode_jwt_payload(id_token: str) -> dict[str, Any]:
    """Return the full decoded payload of an unverified JWT id_token.

    The token has already been authenticated via the OAuth2 code exchange over
    TLS to the issuer; we only inspect the payload to extract claims such as
    ``sub`` (for ``unique_id``) and ``name`` / ``email`` (for the entry title).
    """
    payload_b64 = id_token.split(".")[1]
    # Add base64 padding; urlsafe b64 in JWTs omits ``=``.
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return cast(dict[str, Any], json.loads(base64.urlsafe_b64decode(payload_b64)))


def _display_name_from_claims(payload: dict[str, Any]) -> str | None:
    """Return the first non-empty display claim, or ``None`` when none qualifies.

    Walks the OIDC display-claim preference chain (``name`` then ``email``),
    treating present-but-empty strings and non-string values as absent so the
    caller falls back to a generic title rather than rendering ``" ()"``.
    """
    for key in ("name", "email"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None
