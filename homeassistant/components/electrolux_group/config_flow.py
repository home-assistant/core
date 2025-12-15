"""Config flow for Electrolux Group integration."""

from collections.abc import Mapping
import logging
from typing import Any, cast

from electrolux_group_developer_sdk.auth.invalid_credentials_exception import (
    InvalidCredentialsException,
)
from electrolux_group_developer_sdk.auth.token_manager import TokenManager
from electrolux_group_developer_sdk.client.appliance_client import ApplianceClient
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.failed_connection_exception import (
    FailedConnectionException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import ElectroluxConfigEntry, ElectroluxData, ElectroluxDiscoveryData
from .const import CONF_REFRESH_TOKEN, DOMAIN, NEW_APPLIANCE, USER_AGENT
from .coordinator import ElectroluxDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


class ElectroluxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Electrolux Group integration."""

    def __init__(self) -> None:
        """Initialize the Electrolux flow."""
        super().__init__()
        self._discovered_info: ApplianceData
        self._entry: ElectroluxConfigEntry

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step of the config flow."""

        errors = {}

        _LOGGER.debug(user_input)

        if user_input is not None:
            try:
                token_manager, _appliance_client = await self._authenticate_user(
                    user_input
                )

                # Don't allow the same device or service to be able to be set up twice
                await self.async_set_unique_id(token_manager.get_user_id())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title="Electrolux", data=user_input)
            except AbortFlow:
                raise
            except InvalidCredentialsException as e:
                _LOGGER.error("Missing credentials - %s", e)
                errors["base"] = "auth_failed"
            except FailedConnectionException as e:
                _LOGGER.error("Connection with client failed - %s", e)
                errors["base"] = "cannot_connect"
            except Exception as e:  # noqa: BLE001
                _LOGGER.error("Storing credentials failed - %s", e)
                errors["base"] = "unknown"

        return self._get_form(step_id="user", errors=errors)

    async def async_step_electrolux_discovery(
        self, discovery_data: ElectroluxDiscoveryData
    ) -> config_entries.ConfigFlowResult:
        """Handle Electrolux device discovered via API."""
        appliance = discovery_data.discovered_appliance
        entry = discovery_data.entry
        appliance_id = appliance.appliance.applianceId

        _LOGGER.info(
            "Discovered new Electrolux appliance: %s",
            appliance_id,
        )

        unique_id = appliance_id
        if not unique_id:
            return self.async_abort(reason="missing_id")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        self._discovered_info = appliance
        self._entry = entry
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Ask user to confirm adding the discovered appliance."""
        if user_input is not None:
            data = cast(ElectroluxData, self._entry.runtime_data)

            client = data.client

            appliance = self._discovered_info
            appliance_id = appliance.appliance.applianceId

            coordinator = ElectroluxDataUpdateCoordinator(
                self.hass, self._entry, client=client, applianceId=appliance_id
            )
            await coordinator.async_refresh()
            client.add_listener(appliance_id, coordinator.callback_handle_event)
            data.coordinators[appliance_id] = coordinator

            # Notify all platforms
            async_dispatcher_send(
                self.hass, NEW_APPLIANCE, self._entry.entry_id, self._discovered_info
            )

            persistent_notification.async_create(
                self.hass,
                f"New Electrolux appliance {appliance.appliance.applianceName} added.",
                title="Electrolux Group",
            )
            return self.async_abort(reason="added_to_existing_entry")

        if self._discovered_info.details:
            brand = self._discovered_info.details.applianceInfo.brand
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "device": self._discovered_info.appliance.applianceName,
                "brand": brand or "Electrolux Group",
            },
        )

    async def _authenticate_user(
        self, user_input: Mapping[str, Any]
    ) -> tuple[TokenManager, ApplianceClient]:
        token_manager = TokenManager(
            access_token=user_input[CONF_ACCESS_TOKEN],
            refresh_token=user_input[CONF_REFRESH_TOKEN],
            api_key=user_input[CONF_API_KEY],
        )

        token_manager.ensure_credentials()

        appliance_client = ApplianceClient(
            token_manager=token_manager, external_user_agent=USER_AGENT
        )

        # Test a connection in the config flow
        await appliance_client.test_connection()

        return token_manager, appliance_client

    def _get_form(
        self, step_id: str, errors: dict[str, str]
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Required(CONF_REFRESH_TOKEN): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "portal_link": "https://developer.electrolux.one/generateToken"
            },
        )
