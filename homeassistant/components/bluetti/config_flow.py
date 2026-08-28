"""Copyright (C) 2025 BLUETTI Corporation."""

from collections.abc import Mapping
import logging
from typing import Any, override

from pybluetti import ProductClient, UnifyResponse
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import BluettiConfigEntry
from .application_credentials import async_ensure_default_credential
from .const import (
    ACCOUNT_UNIQUE_ID,
    DOMAIN,
    EVENT_TOKEN_EXPIRED,
    GATEWAY_URL,
    INTEGRATION_NAME,
)
from .oauth import OAuth2FlowHandler
from .options_flow import BluettiOptionsFlowHandler

__LOGGER__ = logging.getLogger(__name__)


class BluettiConfigFlow(OAuth2FlowHandler, domain=DOMAIN):
    """BLUETTI Custom Integration config flow."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        await async_ensure_default_credential(self.hass)
        return await super().async_step_user(user_input)

    @override
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration request by re-running the OAuth2 login."""
        return await super().async_step_reconfigure(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    @override
    async def async_step_select_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let user select devices after OAuth2 login."""
        if user_input is not None:
            try:
                result = await self._product_client.bind_devices(
                    {"bindSnList": user_input["devices"]}
                )
            except Exception as err:  # noqa: BLE001 - cloud SDK call at a system boundary; any failure aborts the flow
                __LOGGER__.error("Failed to bind BLUETTI devices: %s", err)
                return self.async_abort(reason="cannot_connect")

            # bind_devices() doesn't raise on a rejected bind - check msgCode.
            if not (isinstance(result, UnifyResponse) and result.msgCode == 0):
                __LOGGER__.error("Failed to bind BLUETTI devices: %s", result)
                return self.async_abort(reason="cannot_connect")

            # Prevent configuring the same BLUETTI account twice: look up any
            # existing entry by its unique_id instead of matching on title.
            await self.async_set_unique_id(ACCOUNT_UNIQUE_ID)
            existing_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, ACCOUNT_UNIQUE_ID
            )
            if existing_entry is None:
                # Entries created before this integration used a stable
                # unique_id have none set; fall back to the old title match
                # once and backfill the unique_id so future lookups work.
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if (
                        entry.unique_id is None
                        and entry.title == f"{INTEGRATION_NAME} Power Integration"
                    ):
                        self.hass.config_entries.async_update_entry(
                            entry, unique_id=ACCOUNT_UNIQUE_ID
                        )
                        existing_entry = entry
                        break

            if existing_entry and self.source not in (
                SOURCE_REAUTH,
                SOURCE_RECONFIGURE,
            ):
                # A plain "Add Integration" flow finding an existing entry
                # means a second account - reject, don't merge and overwrite
                # the first account's token.
                return self.async_abort(reason="already_configured")

            if existing_entry:
                # Merge into the existing integration entry
                existing_devices = existing_entry.options.get("devices", [])
                existing_products = existing_entry.data.get("products", [])

                # Merge the device list (deduplicated)
                merged_devices = list(set(existing_devices + user_input["devices"]))

                # Merge the product data (deduplicated)
                existing_product_sns = {
                    p.get("sn") if isinstance(p, dict) else p.sn
                    for p in existing_products
                }
                new_products = [
                    p for p in self._products if p.sn not in existing_product_sns
                ]
                merged_products = existing_products + [
                    p.model_dump() if hasattr(p, "model_dump") else p
                    for p in new_products
                ]

                token_updates = {
                    "auth_implementation": self._oauth_data["auth_implementation"],
                    "token": self._oauth_data["token"],
                    "products": merged_products,
                }

                # Apply both data and options in one call so
                # _abort_if_unique_id_configured()'s own data= update below
                # is a no-op and doesn't reload the entry a second time.
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={**existing_entry.data, **token_updates},
                    options={**existing_entry.options, "devices": merged_devices},
                )

                self._abort_if_unique_id_configured(
                    updates=token_updates,
                    reload_on_update=True,
                    error="success",
                )
            # Create a new integration entry
            return self.async_create_entry(
                title=f"{INTEGRATION_NAME} Power Integration",
                data={
                    "auth_implementation": self._oauth_data["auth_implementation"],
                    "token": self._oauth_data["token"],
                    "products": [p.model_dump() for p in self._products],
                },
                options=user_input,
            )

        http_session = async_get_clientsession(self.hass)
        access_token = self._oauth_data["token"]["access_token"]
        product_client = ProductClient(
            http_session,
            GATEWAY_URL,
            access_token,
            on_auth_expired=lambda: self.hass.bus.fire(EVENT_TOKEN_EXPIRED),
        )
        try:
            products = await product_client.get_user_products()
        except Exception as err:  # noqa: BLE001 - cloud SDK call at a system boundary; any failure aborts the flow
            __LOGGER__.error("Failed to fetch BLUETTI products: %s", err)
            return self.async_abort(reason="cannot_connect")

        # products.data is `T | None` on the wire - can be omitted entirely.
        if not products.data:
            return self.async_abort(reason="no_devices_available")

        self._product_client = product_client
        self._products = products.data

        # Collect the devices already added to any existing entry
        integrated_devices = set()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            integrated_devices.update(entry.options.get("devices", []))

        # Filter out devices that have already been added
        available_devices = {
            prod.sn: f"{prod.name} - {prod.sn}"
            for prod in products.data
            if prod.sn not in integrated_devices
        }

        # reconfigure token
        if "entry_id" in self.context:
            cur_entry = self.hass.config_entries.async_get_entry(
                self.context["entry_id"]
            )
            if cur_entry is None:
                return self.async_abort(reason="reconfigure_failed")

            # No real account ID exists to compare - device-serial overlap
            # with cur_entry's already-enabled devices is the closest proxy.
            reauthed_sns = {prod.sn for prod in products.data}
            enabled_sns = set(cur_entry.options.get("devices", []))
            if not enabled_sns <= reauthed_sns:
                __LOGGER__.error(
                    "Reconfigure token: authenticated account is missing "
                    "%s already-enabled device(s) - refusing to update the "
                    "stored token, likely a different BLUETTI account",
                    enabled_sns - reauthed_sns,
                )
                return self.async_abort(reason="wrong_account")

            __LOGGER__.info("reconfigure token")
            new_data = {**cur_entry.data, "token": self._oauth_data["token"]}
            self.hass.config_entries.async_update_entry(cur_entry, data=new_data)
            await self.hass.config_entries.async_reload(cur_entry.entry_id)
            return self.async_abort(reason="success")

        # All the account's devices are already added
        if not available_devices:
            return self.async_abort(reason="all_devices_exists")

        schema = vol.Schema(
            {
                vol.Required(
                    "devices", default=list(available_devices.keys())
                ): cv.multi_select(available_devices)
            }
        )

        return self.async_show_form(
            step_id="select_devices",
            data_schema=schema,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: BluettiConfigEntry,
    ) -> BluettiOptionsFlowHandler:
        """Return the options flow used to add more devices later."""
        return BluettiOptionsFlowHandler()
