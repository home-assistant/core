"""Config flow for the Novy Cooker Hood integration."""

import asyncio
from typing import Any

from rf_protocols.codes.novy.cooker_hood import NovyCookerHoodButton
import voluptuous as vol

from homeassistant.components.radio_frequency import (
    async_get_transmitters,
    async_send_command,
)
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_CODE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CODE_MAX,
    CODE_MIN,
    CONF_TRANSMITTER,
    DEFAULT_CODE,
    DOMAIN,
    FREQUENCY,
    MODULATION,
)

_CODE_OPTIONS = [str(code) for code in range(CODE_MIN, CODE_MAX + 1)]
_TOGGLE_GAP = 1.5


class NovyCookerHoodConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Novy Cooker Hood."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._transmitter_entity_id: str | None = None
        self._transmitter_id: str | None = None
        self._code: int = DEFAULT_CODE

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a transmitter and code for a new entry."""
        return await self._async_step_picker("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a transmitter and code to update an existing entry."""
        if user_input is None and self._transmitter_entity_id is None:
            entry = self._get_reconfigure_entry()
            transmitter = er.async_get(self.hass).async_get(
                entry.data[CONF_TRANSMITTER]
            )
            self._transmitter_entity_id = transmitter.entity_id if transmitter else None
            self._code = entry.data[CONF_CODE]
        return await self._async_step_picker("reconfigure", user_input)

    async def _async_step_picker(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Show the transmitter+code picker shared by user and reconfigure steps."""
        try:
            transmitters = async_get_transmitters(self.hass, FREQUENCY, MODULATION)
        except HomeAssistantError:
            return self.async_abort(reason="no_transmitters")

        if not transmitters:
            return self.async_abort(
                reason="no_compatible_transmitters",
                description_placeholders={
                    "frequency": f"{FREQUENCY / 1_000_000} MHz",
                    "modulation": MODULATION.name,
                },
            )

        if user_input is not None:
            registry = er.async_get(self.hass)
            entity_entry = registry.async_get(user_input[CONF_TRANSMITTER])
            assert entity_entry is not None
            code = int(user_input[CONF_CODE])
            unique_id = f"{entity_entry.id}_{code}"
            await self.async_set_unique_id(unique_id)
            if self.source == SOURCE_RECONFIGURE:
                existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, unique_id
                )
                reconfigure_entry = self._get_reconfigure_entry()
                if existing and existing.entry_id != reconfigure_entry.entry_id:
                    return self.async_abort(reason="already_configured")
            else:
                self._abort_if_unique_id_configured()
            self._transmitter_entity_id = entity_entry.entity_id
            self._transmitter_id = entity_entry.id
            self._code = code
            return await self.async_step_test_light()

        schema: dict[Any, Any] = {
            vol.Required(
                CONF_TRANSMITTER,
                default=self._transmitter_entity_id or vol.UNDEFINED,
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=transmitters),
            ),
            vol.Required(CONF_CODE, default=str(self._code)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_CODE_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="code",
                )
            ),
        }
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(schema),
        )

    async def async_step_test_light(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Toggle the hood light on then off so it ends in its starting state."""
        assert self._transmitter_entity_id is not None
        command = NovyCookerHoodButton.LIGHT.to_command(channel=self._code)
        try:
            await async_send_command(self.hass, self._transmitter_entity_id, command)
            await asyncio.sleep(_TOGGLE_GAP)
            await async_send_command(self.hass, self._transmitter_entity_id, command)
        except HomeAssistantError:
            return await self.async_step_test_failed()
        return self.async_show_menu(
            step_id="test_light",
            menu_options=["finish", "retry"],
            description_placeholders={"code": str(self._code)},
        )

    async def async_step_test_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-show the failure menu (only Retry available)."""
        return self.async_show_menu(
            step_id="test_failed",
            menu_options=["retry"],
            description_placeholders={"code": str(self._code)},
        )

    async def async_step_retry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Return to the picker step matching the current source."""
        if self.source == SOURCE_RECONFIGURE:
            return await self.async_step_reconfigure()
        return await self.async_step_user()

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create or update the config entry."""
        assert self._transmitter_id is not None
        data = {CONF_TRANSMITTER: self._transmitter_id, CONF_CODE: self._code}
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=data,
                unique_id=f"{self._transmitter_id}_{self._code}",
            )
        return self.async_create_entry(title="Novy Cooker Hood", data=data)
