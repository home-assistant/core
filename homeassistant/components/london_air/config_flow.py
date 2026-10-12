"""Config flow for the London Air integration."""

import asyncio
from collections.abc import Mapping
from typing import Any, override

import aiohttp
import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import AUTHORITIES, CONF_LOCATIONS, DOMAIN, REQUEST_TIMEOUT, URL


def _import_deadline() -> float:
    """Return the deadline margin for waiting on a concurrent import."""
    # Two sequential REQUEST_TIMEOUT-bounded requests (connection test and
    # first refresh) can elapse while the entry stays SETUP_IN_PROGRESS;
    # add a margin so we do not give up just before the entry is ready.
    return 2 * (REQUEST_TIMEOUT.total or 10.0) + 5.0


class LondonAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a London Air config flow."""

    VERSION = 1

    async def _test_connection(self) -> None:
        """Verify the API is reachable, raising on failure."""
        response = await async_get_clientsession(self.hass).get(
            URL, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        response.release()

    def _schema(self, default: list[str]) -> probatio.Schema:
        """Build the locations selection schema."""
        return probatio.Schema(
            {
                probatio.Required(CONF_LOCATIONS, default=default): cv.multi_select(
                    AUTHORITIES
                )
            }
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_LOCATIONS]:
                errors[CONF_LOCATIONS] = "required"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                try:
                    await self._test_connection()
                except aiohttp.ClientError, TimeoutError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title="London Air", data=user_input)

        default = AUTHORITIES if user_input is None else user_input[CONF_LOCATIONS]
        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(default),
            errors=errors,
        )

    async def async_step_import(
        self, import_config: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        try:
            entry = await self.async_set_unique_id(DOMAIN)
        except AbortFlow:
            # A concurrent import is creating the entry; wait for its
            # outcome so this block reports the same result.
            return self.async_abort(
                reason=await self._async_await_creator_outcome(import_config)
            )
        if entry is not None:
            self._merge_import_locations(entry, import_config)
            return self.async_abort(reason="already_configured")
        try:
            await self._test_connection()
        except aiohttp.ClientError, TimeoutError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title="London Air",
            data={CONF_LOCATIONS: list(import_config[CONF_LOCATIONS])},
        )

    def _merge_import_locations(
        self, entry: ConfigEntry, import_config: Mapping[str, Any]
    ) -> None:
        """Merge imported locations into an existing entry."""
        locations = list(entry.data[CONF_LOCATIONS])
        for location in import_config[CONF_LOCATIONS]:
            if location not in locations:
                locations.append(location)
        if locations != entry.data[CONF_LOCATIONS]:
            self.hass.config_entries.async_update_entry(
                entry, data={CONF_LOCATIONS: locations}
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)

    async def _async_await_creator_outcome(
        self, import_config: Mapping[str, Any]
    ) -> str:
        """Wait for the concurrent import's outcome and return the abort reason."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _import_deadline()
        while True:
            entry = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, DOMAIN
            )
            if (
                entry is not None
                and entry.state is not ConfigEntryState.SETUP_IN_PROGRESS
            ):
                self._merge_import_locations(entry, import_config)
                return "already_configured"
            if entry is None and not self._creator_flow_in_progress():
                # The concurrent import finished without creating an entry.
                return "cannot_connect"
            if loop.time() >= deadline:
                return "cannot_connect"
            await asyncio.sleep(0.1)

    def _creator_flow_in_progress(self) -> bool:
        """Return True if the concurrent import flow is still running."""
        return any(
            flow["flow_id"] != self.flow_id
            for flow in self.hass.config_entries.flow.async_progress_by_handler(
                DOMAIN,
                include_uninitialized=True,
                match_context={"unique_id": DOMAIN},
            )
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure step."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            if not user_input[CONF_LOCATIONS]:
                errors[CONF_LOCATIONS] = "required"
            else:
                try:
                    await self._test_connection()
                except aiohttp.ClientError, TimeoutError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_update_reload_and_abort(
                        entry, data_updates=user_input
                    )

        default = (
            entry.data[CONF_LOCATIONS]
            if user_input is None
            else user_input[CONF_LOCATIONS]
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._schema(default),
            errors=errors,
        )
