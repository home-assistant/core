"""Config flow for the OpenWrt (ubus) integration."""

from types import MappingProxyType
from typing import Any, override

from openwrt.ubus import Ubus
import probatio

from homeassistant.components.device_tracker.const import CONF_CONSIDER_HOME
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_DHCP_SOFTWARE,
    DEFAULT_DHCP_SOFTWARE,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DHCP_SOFTWARES,
    DOMAIN,
    SUBENTRY_TYPE_ROUTER,
)

HUB_TITLE = "OpenWrt (ubus)"

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
        probatio.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
        probatio.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
        probatio.Required(
            CONF_DHCP_SOFTWARE, default=DEFAULT_DHCP_SOFTWARE
        ): SelectSelector(
            SelectSelectorConfig(
                options=DHCP_SOFTWARES,
                translation_key="dhcp_software",
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_CONSIDER_HOME): NumberSelector(
            NumberSelectorConfig(
                # Below the polling interval the window rarely means anything.
                min=30,
                max=86400,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="s",
            )
        ),
    }
)


def validate_connection(data: dict[str, Any]) -> None:
    """Validate that we can log in to the router with the given configuration."""
    scheme = "https" if data.get(CONF_SSL, DEFAULT_SSL) else "http"
    ubus = Ubus(
        f"{scheme}://{data[CONF_HOST]}/ubus",
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        verify=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
    )
    try:
        session_id = ubus.connect()
    except PermissionError as err:
        raise InvalidAuth from err
    except (ConnectionError, TypeError) as err:
        # openwrt-ubus-rpc raises TypeError when the HTTP request itself fails.
        raise CannotConnect from err
    if session_id is None:
        raise InvalidAuth


def _router_subentry_data(data: dict[str, Any]) -> ConfigSubentryData:
    """Return the subentry data for a router configuration."""
    return ConfigSubentryData(
        data=data,
        subentry_type=SUBENTRY_TYPE_ROUTER,
        title=data[CONF_HOST],
        unique_id=data[CONF_HOST],
    )


class UbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenWrt (ubus)."""

    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types this integration supports."""
        return {SUBENTRY_TYPE_ROUTER: RouterSubentryFlow}

    @staticmethod
    @override
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return UbusOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step.

        The entry is a pure hub, so a second entry flow is rejected; routers
        are added as subentries of the existing entry.
        """
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(validate_connection, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(
                    title=HUB_TITLE,
                    data={},
                    subentries=[_router_subentry_data(user_input)],
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a configuration from configuration.yaml."""
        entries = self._async_current_entries()
        # Find the hub, creating it below if the install is legacy: the
        # entry which is set up first becomes the hub, so the import joins
        # the same one the setup migration will use.
        hub = next((entry for entry in entries if not entry.data), None)
        if hub is None and entries:
            hub = min(entries, key=lambda entry: entry.entry_id)
        hosts = {entry.data[CONF_HOST] for entry in entries if entry.data} | {
            subentry.unique_id
            for entry in entries
            for subentry in entry.subentries.values()
            if subentry.unique_id
        }
        if import_data[CONF_HOST] in hosts:
            return self.async_abort(reason="already_configured")

        try:
            await self.hass.async_add_executor_job(validate_connection, import_data)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")

        if hub is None:
            return self.async_create_entry(
                title=HUB_TITLE,
                data={},
                subentries=[_router_subentry_data(import_data)],
            )

        self.hass.config_entries.async_add_subentry(
            hub,
            ConfigSubentry(
                data=MappingProxyType(import_data),
                subentry_type=SUBENTRY_TYPE_ROUTER,
                title=import_data[CONF_HOST],
                unique_id=import_data[CONF_HOST],
            ),
        )
        return self.async_abort(reason="already_configured")


class RouterSubentryFlow(ConfigSubentryFlow):
    """Handle the subentry flow for adding and modifying a router."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the step to add a router."""
        entry = self._get_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if any(
                subentry.unique_id == user_input[CONF_HOST]
                for subentry in entry.subentries.values()
            ):
                errors["base"] = "already_configured"
            else:
                try:
                    await self.hass.async_add_executor_job(
                        validate_connection, user_input
                    )
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_HOST],
                        data=user_input,
                        unique_id=user_input[CONF_HOST],
                    )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the step to change a router.

        Finishes with an update-and-abort: the entry reloads via its update
        listener, and the combined update-and-reload helper is unusable for
        an entry with update listeners.
        """
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if any(
                other.unique_id == user_input[CONF_HOST]
                for other in entry.subentries.values()
                if other is not subentry
            ):
                errors["base"] = "already_configured"
            else:
                try:
                    await self.hass.async_add_executor_job(
                        validate_connection, user_input
                    )
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                else:
                    return self.async_update_and_abort(
                        entry,
                        subentry,
                        data=user_input,
                        title=user_input[CONF_HOST],
                    )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, dict(subentry.data)
            ),
            errors=errors,
        )


class UbusOptionsFlow(OptionsFlow):
    """Handle the options flow for the OpenWrt (ubus) entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect to the router."""


class InvalidAuth(Exception):
    """Error to indicate the credentials are invalid."""
