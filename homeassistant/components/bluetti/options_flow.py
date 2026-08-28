"""Options flow for the BLUETTI integration.

Lets the user add devices bound to their BLUETTI account after the initial
setup, without going through the OAuth2 login flow again (the stored token
is reused).
"""

import logging
from typing import Any

from pybluetti import ProductClient, UnifyResponse, UserProduct
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import EVENT_TOKEN_EXPIRED
from .profile.application_profile import APPLICATION_PROFILE

__LOGGER__ = logging.getLogger(__name__)


class BluettiOptionsFlowHandler(OptionsFlow):
    """Handle an options flow to add more BLUETTI devices to an existing entry."""

    _product_client: ProductClient
    _products: list[UserProduct]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick additional devices from their BLUETTI account."""
        entry: ConfigEntry = self.config_entry

        if user_input is not None:
            selected = user_input["devices"]
            try:
                result = await self._product_client.bind_devices(
                    {"bindSnList": selected}
                )
            except Exception as err:  # noqa: BLE001 - cloud SDK call at a system boundary; any failure aborts the flow
                __LOGGER__.error("Failed to bind BLUETTI devices: %s", err)
                return self.async_abort(reason="cannot_connect")

            # bind_devices() returns a plain str for a non-JSON server
            # response, and a nonzero msgCode without raising - either way
            # the devices were not actually bound, so this must not fall
            # through and persist them as though it succeeded.
            if not (isinstance(result, UnifyResponse) and result.msgCode == 0):
                __LOGGER__.error("Failed to bind BLUETTI devices: %s", result)
                return self.async_abort(reason="cannot_connect")

            current_devices = entry.options.get("devices", [])
            merged_devices = list(set(current_devices) | set(selected))

            existing_products = entry.data.get("products", [])
            existing_sns = {
                p.get("sn") if isinstance(p, dict) else p.sn for p in existing_products
            }
            new_products = [p for p in self._products if p.sn not in existing_sns]
            merged_products = existing_products + [p.model_dump() for p in new_products]

            merged_options = {"devices": merged_devices}

            # Applying the same options here first means OptionsFlowManager's
            # own async_update_entry(entry, options=...) after this step
            # returns finds nothing changed and skips reloading a second
            # time (see ConfigEntries._async_update_entry).
            self.hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, "products": merged_products},
                options=merged_options,
            )

            return self.async_create_entry(data=merged_options)

        # ApplicationProfile is a module-level singleton populated by
        # config_flow.py's async_step_user - relying on that having already
        # run in this process is a real cross-test hazard under pytest-xdist
        # (each test file can get its own fresh worker process), so this
        # flow (entered without going through async_step_user again) must
        # load it itself too. Idempotent: re-reads the same static file.
        await APPLICATION_PROFILE.load_config(self.hass)

        http_session = async_get_clientsession(self.hass)
        try:
            # Reading entry.data["token"] directly would skip Home
            # Assistant's refresh path - an options flow opened after the
            # stored access token has expired (but the refresh token is
            # still valid) would otherwise fail as cannot_connect for no
            # real reason. Same OAuth2Session-backed refresh path setup
            # uses in __init__.py.
            implementation = (
                await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    self.hass, entry
                )
            )
            oauth_session = config_entry_oauth2_flow.OAuth2Session(
                self.hass, entry, implementation
            )
            await oauth_session.async_ensure_token_valid()
            access_token = oauth_session.token["access_token"]
            product_client = ProductClient(
                http_session,
                APPLICATION_PROFILE.config["server"]["gateway"],
                access_token,
                on_auth_expired=lambda: self.hass.bus.fire(EVENT_TOKEN_EXPIRED),
            )
            products = await product_client.get_user_products()
        except Exception as err:  # noqa: BLE001 - cloud SDK call at a system boundary; any failure aborts the flow
            __LOGGER__.error("Failed to fetch BLUETTI products: %s", err)
            return self.async_abort(reason="cannot_connect")

        # Checked before iterating products.data below: it's `T | None` on
        # the wire, and a cloud response that omits "data" entirely would
        # otherwise crash the dict comprehension with an unhandled
        # TypeError instead of aborting gracefully.
        if not products.data:
            return self.async_abort(reason="no_devices_available")

        self._product_client = product_client
        self._products = products.data

        enabled_devices = set(entry.options.get("devices", []))
        available_devices = {
            product.sn: f"{product.name} - {product.sn}"
            for product in products.data
            if product.sn not in enabled_devices
        }

        if not available_devices:
            return self.async_abort(reason="all_devices_exists")

        schema = vol.Schema(
            {
                vol.Required(
                    "devices",
                    default=list(available_devices.keys()),
                ): cv.multi_select(available_devices)
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
