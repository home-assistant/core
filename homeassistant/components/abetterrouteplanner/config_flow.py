"""Config flow for the A Better Routeplanner integration."""

import logging
from typing import Any, override

from aioabrp import (
    AbrpApiError,
    AbrpAuthError,
    AbrpClient,
    AbrpVehicle,
    StaticAuth,
    parse_unverified_identity,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
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
    _title: str

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @override
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

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a successful OAuth2 authorization.

        Fetch the user's garage, stash it, and hand off to
        ``async_step_pick_vehicles`` so the user can pick which vehicles to
        track.
        """
        # The IdP issues id_token via the authorization_code grant (the scope
        # is ``oidc``). A missing id_token here means the IdP misbehaved; abort
        # safely rather than silently accept a token that we can't bind to a
        # verified account.
        id_token = data["token"].get("id_token")
        if id_token is None:
            return self.async_abort(reason="oauth_error")
        # AbrpAuthError here means a bad id_token — distinct from the API-auth
        # use of the same exception in the async_get_vehicles call below.
        try:
            identity = parse_unverified_identity(id_token)
        except AbrpAuthError:
            return self.async_abort(reason="oauth_error")
        await self.async_set_unique_id(identity.subject)

        self._abort_if_unique_id_configured()

        self._title = (
            f"{self.flow_impl.name} ({identity.display_name})"
            if identity.display_name
            else self.flow_impl.name
        )

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
                return self.async_create_entry(
                    title=self._title,
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
