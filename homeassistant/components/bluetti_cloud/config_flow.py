"""Config flow for the BLUETTI Cloud integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from pybluetti import ProductClient, UnifyResponse

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .application_credentials import async_ensure_default_credential
from .const import ACCOUNT_UNIQUE_ID, DOMAIN, GATEWAY_URL, INTEGRATION_NAME
from .oauth import OAuth2FlowHandler

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
        """Bind every device on the account, batteries-included.

        There is no separate device-picker step: every product on the
        authenticated account is bound and added, and the user disables
        individual devices afterward if they don't want them, the same as
        any other Home Assistant integration. Named async_step_select_devices
        (not async_step_bind_devices) only because OAuth2FlowHandler's
        async_oauth_create_entry calls this exact step name.
        """
        http_session = async_get_clientsession(self.hass)
        access_token = self._oauth_data["token"]["access_token"]
        product_client = ProductClient(http_session, GATEWAY_URL, access_token)
        try:
            products = await product_client.get_user_products()
        except Exception as err:  # noqa: BLE001 - cloud SDK call at a system boundary; any failure aborts the flow
            __LOGGER__.error("Failed to fetch BLUETTI products: %s", err)
            return self.async_abort(reason="cannot_connect")

        # A failed application-level response (nonzero msgCode) doesn't
        # raise - it would otherwise look like a real "no devices" account.
        if not products.is_ok():
            __LOGGER__.error("Failed to fetch BLUETTI products: %s", products)
            return self.async_abort(reason="cannot_connect")

        # products.data is `T | None` on the wire - can be omitted entirely.
        all_products = products.data or []

        # Reauth/reconfigure: refresh the stored token and re-bind whatever
        # the account currently has (picks up devices added since setup,
        # batteries-included), but never create a second entry or show a
        # form - both always carry entry_id in context.
        if "entry_id" in self.context:
            cur_entry = self.hass.config_entries.async_get_entry(
                self.context["entry_id"]
            )
            if cur_entry is None:
                return self.async_abort(reason="reconfigure_failed")

            # No real account ID exists to compare - device-serial overlap
            # with what this entry bound last time is the closest proxy.
            # Only rejected on zero overlap so an account that has
            # legitimately lost every previously-bound device (all unbound
            # server-side) can still reauth to reconcile that.
            reauthed_sns = {prod.sn for prod in all_products}
            known_sns = set(cur_entry.data.get("device_sns", []))
            if known_sns and not (known_sns & reauthed_sns):
                __LOGGER__.error(
                    "Reconfigure token: authenticated account shares none of "
                    "%s previously-bound device(s) - refusing to update the "
                    "stored token, likely a different BLUETTI account",
                    known_sns,
                )
                return self.async_abort(reason="wrong_account")

            if all_products:
                try:
                    result = await product_client.bind_devices(
                        {"bindSnList": [p.sn for p in all_products]}
                    )
                except Exception as err:  # noqa: BLE001 - cloud SDK call at a system boundary; any failure aborts the flow
                    __LOGGER__.error("Failed to bind BLUETTI devices: %s", err)
                    return self.async_abort(reason="cannot_connect")
                if not (isinstance(result, UnifyResponse) and result.msgCode == 0):
                    __LOGGER__.error("Failed to bind BLUETTI devices: %s", result)
                    return self.async_abort(reason="cannot_connect")

            # auth_implementation too, not just token - the user could have
            # picked a different Application Credential during this login.
            new_data = {
                **cur_entry.data,
                "auth_implementation": self._oauth_data["auth_implementation"],
                "token": self._oauth_data["token"],
                "device_sns": [p.sn for p in all_products],
            }
            return self.async_update_reload_and_abort(cur_entry, data=new_data)

        if not all_products:
            return self.async_abort(reason="no_devices_available")

        # Entries created before this integration used a stable unique_id
        # have none set; fall back to the old title match once and backfill
        # the unique_id so the standard check below can find it too.
        if (
            self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, ACCOUNT_UNIQUE_ID
            )
            is None
        ):
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if (
                    entry.unique_id is None
                    and entry.title == f"{INTEGRATION_NAME} Power Integration"
                ):
                    self.hass.config_entries.async_update_entry(
                        entry, unique_id=ACCOUNT_UNIQUE_ID
                    )
                    break

        # Prevent configuring the same BLUETTI account twice: a plain "Add
        # Integration" flow finding an existing entry means a second
        # account - reject before binding anything server-side.
        await self.async_set_unique_id(ACCOUNT_UNIQUE_ID)
        self._abort_if_unique_id_configured()

        try:
            result = await product_client.bind_devices(
                {"bindSnList": [p.sn for p in all_products]}
            )
        except Exception as err:  # noqa: BLE001 - cloud SDK call at a system boundary; any failure aborts the flow
            __LOGGER__.error("Failed to bind BLUETTI devices: %s", err)
            return self.async_abort(reason="cannot_connect")

        # bind_devices() doesn't raise on a rejected bind - check msgCode.
        if not (isinstance(result, UnifyResponse) and result.msgCode == 0):
            __LOGGER__.error("Failed to bind BLUETTI devices: %s", result)
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=f"{INTEGRATION_NAME} Power Integration",
            data={
                "auth_implementation": self._oauth_data["auth_implementation"],
                "token": self._oauth_data["token"],
                "device_sns": [p.sn for p in all_products],
            },
        )
