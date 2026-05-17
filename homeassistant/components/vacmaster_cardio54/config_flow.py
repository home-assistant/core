"""Config flow for the Vacmaster Cardio54 integration."""

import random
from typing import Any

from rf_protocols.commands.ev1527 import EV1527Command
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_DEVICE_ID,
    CONF_TRANSMITTER,
    DATA_POWER,
    DATA_SPEEDS,
    DEVICE_ID_BITS,
    DOMAIN,
    FRAME_REPEATS,
    FREQUENCY,
    MODULATION,
    PAIR_FRAME_REPEATS,
    TIMEBASE_US,
)


class VacmasterCardio54ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vacmaster Cardio54."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._transmitter_entity_id: str | None = None
        self._transmitter_id: str | None = None
        self._device_id: int | None = None

    def _generate_device_id(self, transmitter_id: str) -> int:
        """Return a random 20-bit device ID not yet used on this transmitter.

        Different transmitters can safely reuse the same device ID; the
        config entry's unique_id is ``{transmitter}_{device_id}``, so a
        device-ID collision only matters when both transmitters match.

        Raises ``HomeAssistantError`` in the pathological case where the
        20-bit ID space on this transmitter is exhausted (~1M entries) — a
        bounded retry keeps the event loop from blocking forever.
        """
        used = {
            entry.data[CONF_DEVICE_ID]
            for entry in self._async_current_entries()
            if entry.data.get(CONF_TRANSMITTER) == transmitter_id
        }
        for _ in range(1000):
            candidate = random.getrandbits(DEVICE_ID_BITS)
            if candidate not in used:
                return candidate
        raise HomeAssistantError(
            "Could not allocate a unique 20-bit device ID on this transmitter"
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a transmitter and assign a new RF identity to the fan."""
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
            entity_entry = er.async_get(self.hass).async_get(
                user_input[CONF_TRANSMITTER]
            )
            assert entity_entry is not None
            self._transmitter_entity_id = entity_entry.entity_id
            self._transmitter_id = entity_entry.id
            self._device_id = self._generate_device_id(self._transmitter_id)
            await self.async_set_unique_id(
                f"{self._transmitter_id}_{self._device_id:05X}"
            )
            self._abort_if_unique_id_configured()
            return await self.async_step_pair()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TRANSMITTER): selector.EntitySelector(
                        selector.EntitySelectorConfig(include_entities=transmitters),
                    ),
                }
            ),
        )

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Send the pairing burst once the fan is in pairing mode."""
        if user_input is None:
            return self.async_show_form(step_id="pair", data_schema=vol.Schema({}))

        try:
            await self._async_send(DATA_POWER, PAIR_FRAME_REPEATS)
        except HomeAssistantError:
            return await self.async_step_send_failed()
        return await self.async_step_test()

    async def async_step_send_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the send-failure menu (used by both pair and test steps)."""
        return self.async_show_menu(
            step_id="send_failed",
            menu_options=["retry"],
        )

    async def async_step_test(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Send a speed command and let the user confirm the fan reacted."""
        try:
            await self._async_send(DATA_SPEEDS[0], FRAME_REPEATS)
        except HomeAssistantError:
            return await self.async_step_send_failed()
        return self.async_show_menu(
            step_id="test",
            menu_options=["finish", "retry"],
        )

    async def async_step_retry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Return to the pairing step."""
        return await self.async_step_pair()

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create or update the config entry."""
        assert self._transmitter_id is not None
        assert self._device_id is not None
        data = {
            CONF_TRANSMITTER: self._transmitter_id,
            CONF_DEVICE_ID: self._device_id,
        }
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=data,
                unique_id=f"{self._transmitter_id}_{self._device_id:05X}",
            )
        return self.async_create_entry(title="Vacmaster Cardio54", data=data)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-select the transmitter for an existing fan; the device ID is kept."""
        entry = self._get_reconfigure_entry()
        self._device_id = entry.data[CONF_DEVICE_ID]

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
            entity_entry = er.async_get(self.hass).async_get(
                user_input[CONF_TRANSMITTER]
            )
            assert entity_entry is not None
            unique_id = f"{entity_entry.id}_{self._device_id:05X}"
            existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, unique_id
            )
            if existing and existing.entry_id != entry.entry_id:
                return self.async_abort(reason="already_configured")
            self._transmitter_entity_id = entity_entry.entity_id
            self._transmitter_id = entity_entry.id
            return await self.async_step_finish()

        current = er.async_get(self.hass).async_get(entry.data[CONF_TRANSMITTER])
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TRANSMITTER,
                        default=current.entity_id if current else vol.UNDEFINED,
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(include_entities=transmitters),
                    ),
                }
            ),
        )

    async def _async_send(self, data: int, frame_repeats: int) -> None:
        """Encode and transmit a single EV1527 command during the flow."""
        assert self._transmitter_entity_id is not None
        assert self._device_id is not None
        command = EV1527Command(
            device_id=self._device_id,
            data=data,
            frequency=FREQUENCY,
            timebase_us=TIMEBASE_US,
            frame_repeats=frame_repeats,
        )
        await async_send_command(self.hass, self._transmitter_entity_id, command)
