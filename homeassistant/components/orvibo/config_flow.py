"""Config flow for the orvibo integration."""

import asyncio
import logging
from typing import Any

from orvibo.s20 import S20, S20Exception, discover
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_SWITCH_LIST, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


FULL_EDIT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_MAC): cv.string,
    }
)


class S20ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Orvibo S20 switches."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize an instance of the S20 config flow."""
        self.discovery_task: asyncio.Task | None = None
        self._discovered_switches: dict[str, dict[str, Any]] = {}
        self.chosen_switch: dict[str, Any] = {}

    async def _async_discover(self) -> None:
        def _filter_discovered_switches(
            switches: dict[str, dict[str, Any]],
        ) -> dict[str, dict[str, Any]]:
            # Get existing unique_ids from config entries
            existing_ids = {entry.unique_id for entry in self._async_current_entries()}
            _LOGGER.debug("Existing unique IDs: %s", existing_ids)
            # Build a new filtered dict
            filtered = {}
            for ip, info in switches.items():
                mac_bytes = info.get("mac")
                if not mac_bytes:
                    continue  # skip if no MAC

                unique_id = format_mac(mac_bytes.hex()).lower()
                if unique_id not in existing_ids:
                    filtered[ip] = info
            _LOGGER.debug("New switches: %s", filtered)
            return filtered

        # Discover S20 devices.
        _LOGGER.debug("Discovering S20 switches")

        _unfiltered_switches = await self.hass.async_add_executor_job(discover)
        _LOGGER.debug("All discovered switches: %s", _unfiltered_switches)

        self._discovered_switches = _filter_discovered_switches(_unfiltered_switches)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        return self.async_show_menu(
            step_id="user", menu_options=["start_discovery", "edit"]
        )

    async def _validate_input(self, user_input: dict[str, Any]) -> str | None:
        """Validate user input and discover MAC if missing."""

        if user_input.get(CONF_MAC):
            user_input[CONF_MAC] = format_mac(user_input[CONF_MAC]).lower()
            if len(user_input[CONF_MAC]) != 17 or user_input[CONF_MAC].count(":") != 5:
                return "invalid_mac"

        try:
            device = await self.hass.async_add_executor_job(
                S20,
                user_input[CONF_HOST],
                user_input.get(CONF_MAC),
            )

            if not user_input.get(CONF_MAC):
                # Using private attribute access here since S20 class doesn't have a public method to get the MAC without repeating discovery
                if not device._mac:  # noqa: SLF001
                    return "cannot_discover"
                user_input[CONF_MAC] = format_mac(device._mac.hex()).lower()  # noqa: SLF001

        except S20Exception:
            return "cannot_connect"

        return None

    async def async_step_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit a discovered or manually configured server."""

        errors = {}
        if user_input:
            error = await self._validate_input(user_input)
            if not error:
                await self.async_set_unique_id(user_input[CONF_MAC])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{DEFAULT_NAME} ({user_input[CONF_HOST]})", data=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="edit",
            data_schema=FULL_EDIT_SCHEMA,
            errors=errors,
        )

    async def async_step_start_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if not self.discovery_task:
            self.discovery_task = self.hass.async_create_task(self._async_discover())
            return self.async_show_progress(
                step_id="start_discovery",
                progress_action="start_discovery",
                progress_task=self.discovery_task,
            )
        if self.discovery_task.done():
            try:
                self.discovery_task.result()
            except (S20Exception, OSError) as err:
                _LOGGER.debug("Discovery task failed: %s", err)
            self.discovery_task = None
            return self.async_show_progress_done(
                next_step_id=(
                    "choose_switch" if self._discovered_switches else "discovery_failed"
                )
            )
        return self.async_show_progress(
            step_id="start_discovery",
            progress_action="start_discovery",
            progress_task=self.discovery_task,
        )

    async def async_step_choose_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose manual or discover flow."""
        _chosen_host: str

        if user_input:
            _chosen_host = user_input[CONF_SWITCH_LIST]
            for host, data in self._discovered_switches.items():
                if _chosen_host == host:
                    self.chosen_switch[CONF_HOST] = host
                    self.chosen_switch[CONF_MAC] = format_mac(
                        data[CONF_MAC].hex()
                    ).lower()
                    await self.async_set_unique_id(self.chosen_switch[CONF_MAC])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"{DEFAULT_NAME} ({host})", data=self.chosen_switch
                    )
        _LOGGER.debug("discovered switches: %s", self._discovered_switches)

        _options = {
            host: f"{host} ({format_mac(data[CONF_MAC].hex()).lower()})"
            for host, data in self._discovered_switches.items()
        }
        return self.async_show_form(
            step_id="choose_switch",
            data_schema=vol.Schema({vol.Required(CONF_SWITCH_LIST): vol.In(_options)}),
        )

    async def async_step_discovery_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a failed discovery."""

        return self.async_show_menu(
            step_id="discovery_failed", menu_options=["start_discovery", "edit"]
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        _LOGGER.debug("Importing config: %s", user_input)

        error = await self._validate_input(user_input)
        if error:
            return self.async_abort(reason=error)

        await self.async_set_unique_id(user_input[CONF_MAC])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input.get(CONF_NAME, user_input[CONF_HOST]), data=user_input
        )
