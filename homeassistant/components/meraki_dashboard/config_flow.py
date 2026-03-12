"""Config flow for Meraki Dashboard."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    MerakiDashboardApi,
    MerakiDashboardApiAuthError,
    MerakiDashboardApiConnectionError,
    MerakiDashboardApiError,
)
from .const import (
    CONF_INCLUDED_CLIENTS,
    CONF_NETWORK_ID,
    CONF_NETWORK_NAME,
    CONF_ORGANIZATION_ID,
    CONF_TRACK_BLUETOOTH_CLIENTS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_INFRASTRUCTURE_DEVICES,
    DEFAULT_TIMESPAN_SECONDS,
    DEFAULT_TRACK_BLUETOOTH_CLIENTS,
    DEFAULT_TRACK_CLIENTS,
    DEFAULT_TRACK_INFRASTRUCTURE_DEVICES,
    DOMAIN,
)


class MerakiDashboardConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meraki Dashboard."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_key: str | None = None
        self._organizations: dict[str, str] = {}
        self._organization_id: str | None = None
        self._networks: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MerakiDashboardOptionsFlow:
        """Get the options flow for this handler."""
        return MerakiDashboardOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY].strip()
            api = MerakiDashboardApi(async_get_clientsession(self.hass), self._api_key)
            try:
                organizations = await api.async_get_organizations()
            except MerakiDashboardApiAuthError:
                errors["base"] = "invalid_auth"
            except MerakiDashboardApiConnectionError:
                errors["base"] = "cannot_connect"
            except MerakiDashboardApiError:
                errors["base"] = "unknown"
            else:
                self._organizations = {
                    organization["id"]: organization["name"]
                    for organization in organizations
                    if "id" in organization and "name" in organization
                }
                if not self._organizations:
                    errors["base"] = "no_organizations"
                elif len(self._organizations) == 1:
                    self._organization_id = next(iter(self._organizations))
                    return await self._async_step_load_networks()
                else:
                    return await self.async_step_organization()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_organization(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select Meraki organization."""
        if user_input is not None:
            self._organization_id = user_input[CONF_ORGANIZATION_ID]
            return await self._async_step_load_networks()

        organizations = [
            SelectOptionDict(value=org_id, label=org_name)
            for org_id, org_name in sorted(
                self._organizations.items(), key=lambda item: item[1]
            )
        ]

        return self.async_show_form(
            step_id="organization",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ORGANIZATION_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=organizations, mode=SelectSelectorMode.DROPDOWN
                        )
                    ),
                }
            ),
        )

    async def _async_step_load_networks(self) -> ConfigFlowResult:
        """Load Meraki networks for selected organization."""
        if self._api_key is None or self._organization_id is None:
            return self.async_abort(reason="unknown")

        api = MerakiDashboardApi(async_get_clientsession(self.hass), self._api_key)
        try:
            networks = await api.async_get_networks(self._organization_id)
        except MerakiDashboardApiAuthError:
            return self.async_abort(reason="invalid_auth")
        except MerakiDashboardApiConnectionError:
            return self.async_abort(reason="cannot_connect")
        except MerakiDashboardApiError:
            return self.async_abort(reason="unknown")

        self._networks = {
            network["id"]: network["name"]
            for network in networks
            if "id" in network and "name" in network
        }
        if not self._networks:
            return self.async_abort(reason="no_networks")

        return await self.async_step_network()

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select Meraki network."""
        if user_input is not None and self._api_key and self._organization_id:
            if not (
                user_input[CONF_TRACK_CLIENTS]
                or user_input[CONF_TRACK_BLUETOOTH_CLIENTS]
                or user_input[CONF_TRACK_INFRASTRUCTURE_DEVICES]
            ):
                return self.async_show_form(
                    step_id="network",
                    data_schema=self._network_schema(),
                    errors={"base": "at_least_one_enabled"},
                )
            network_id = user_input[CONF_NETWORK_ID]
            await self.async_set_unique_id(network_id)
            self._abort_if_unique_id_configured()
            network_name = self._networks[network_id]

            return self.async_create_entry(
                title=network_name,
                data={
                    CONF_API_KEY: self._api_key,
                    CONF_ORGANIZATION_ID: self._organization_id,
                    CONF_NETWORK_ID: network_id,
                    CONF_NETWORK_NAME: network_name,
                },
                options={
                    CONF_TRACK_CLIENTS: user_input[CONF_TRACK_CLIENTS],
                    CONF_TRACK_BLUETOOTH_CLIENTS: user_input[
                        CONF_TRACK_BLUETOOTH_CLIENTS
                    ],
                    CONF_TRACK_INFRASTRUCTURE_DEVICES: user_input[
                        CONF_TRACK_INFRASTRUCTURE_DEVICES
                    ],
                    CONF_INCLUDED_CLIENTS: [],
                },
            )

        return self.async_show_form(
            step_id="network", data_schema=self._network_schema()
        )

    def _network_schema(self) -> vol.Schema:
        """Return schema for network selection step."""
        networks = [
            SelectOptionDict(value=network_id, label=network_name)
            for network_id, network_name in sorted(
                self._networks.items(), key=lambda item: item[1]
            )
        ]

        return vol.Schema(
            {
                vol.Required(CONF_NETWORK_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=networks, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required(CONF_TRACK_CLIENTS, default=DEFAULT_TRACK_CLIENTS): bool,
                vol.Required(
                    CONF_TRACK_BLUETOOTH_CLIENTS,
                    default=DEFAULT_TRACK_BLUETOOTH_CLIENTS,
                ): bool,
                vol.Required(
                    CONF_TRACK_INFRASTRUCTURE_DEVICES,
                    default=DEFAULT_TRACK_INFRASTRUCTURE_DEVICES,
                ): bool,
            }
        )


class MerakiDashboardOptionsFlow(OptionsFlowWithReload):
    """Handle options for Meraki Dashboard."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        client_options = await self._async_get_client_options()
        if user_input is not None:
            if not (
                user_input[CONF_TRACK_CLIENTS]
                or user_input[CONF_TRACK_BLUETOOTH_CLIENTS]
                or user_input[CONF_TRACK_INFRASTRUCTURE_DEVICES]
            ):
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._options_schema(client_options),
                    errors={"base": "at_least_one_enabled"},
                )
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self._options_schema(client_options),
        )

    def _options_schema(self, client_options: list[SelectOptionDict]) -> vol.Schema:
        """Build options schema."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_TRACK_CLIENTS,
                    default=self.config_entry.options.get(
                        CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS
                    ),
                ): bool,
                vol.Required(
                    CONF_TRACK_BLUETOOTH_CLIENTS,
                    default=self.config_entry.options.get(
                        CONF_TRACK_BLUETOOTH_CLIENTS,
                        DEFAULT_TRACK_BLUETOOTH_CLIENTS,
                    ),
                ): bool,
                vol.Required(
                    CONF_TRACK_INFRASTRUCTURE_DEVICES,
                    default=self.config_entry.options.get(
                        CONF_TRACK_INFRASTRUCTURE_DEVICES,
                        DEFAULT_TRACK_INFRASTRUCTURE_DEVICES,
                    ),
                ): bool,
                vol.Required(
                    CONF_INCLUDED_CLIENTS,
                    default=self.config_entry.options.get(CONF_INCLUDED_CLIENTS, []),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=client_options,
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
                    )
                ),
            }
        )

    async def _async_get_client_options(self) -> list[SelectOptionDict]:
        """Build list of selectable clients for tracker inclusion."""
        api = MerakiDashboardApi(
            async_get_clientsession(self.hass),
            self.config_entry.data[CONF_API_KEY],
        )
        clients: list[dict[str, Any]] = []
        bluetooth_clients: list[dict[str, Any]] = []

        if self.config_entry.options.get(CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS):
            try:
                clients = await api.async_get_network_clients(
                    self.config_entry.data[CONF_NETWORK_ID],
                    timespan=DEFAULT_TIMESPAN_SECONDS,
                )
            except (
                MerakiDashboardApiAuthError,
                MerakiDashboardApiConnectionError,
                MerakiDashboardApiError,
            ):
                clients = []

        if self.config_entry.options.get(
            CONF_TRACK_BLUETOOTH_CLIENTS, DEFAULT_TRACK_BLUETOOTH_CLIENTS
        ):
            try:
                bluetooth_clients = await api.async_get_network_bluetooth_clients(
                    self.config_entry.data[CONF_NETWORK_ID],
                    timespan=DEFAULT_TIMESPAN_SECONDS,
                )
            except (
                MerakiDashboardApiAuthError,
                MerakiDashboardApiConnectionError,
                MerakiDashboardApiError,
            ):
                bluetooth_clients = []

        options_by_mac: dict[str, SelectOptionDict] = {}
        for client in clients:
            mac = format_mac(client.get("mac", ""))
            if not mac:
                continue
            if mac in options_by_mac:
                continue
            label = (
                client.get("description")
                or client.get("dhcpHostname")
                or client.get("mdnsName")
                or mac
            )
            options_by_mac[mac] = SelectOptionDict(value=mac, label=f"{label} ({mac})")

        for bluetooth_client in bluetooth_clients:
            mac = format_mac(bluetooth_client.get("mac", ""))
            if not mac or mac in options_by_mac:
                continue
            label = (
                bluetooth_client.get("name")
                or bluetooth_client.get("deviceName")
                or mac
            )
            options_by_mac[mac] = SelectOptionDict(value=mac, label=f"{label} ({mac})")

        return sorted(options_by_mac.values(), key=lambda option: option["label"])
