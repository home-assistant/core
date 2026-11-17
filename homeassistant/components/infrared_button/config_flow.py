"""Config flow for the Infrared button integration."""

import asyncio
from contextlib import suppress
from typing import Any, override

import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    InfraredReceivedSignal,
    async_get_emitters,
    async_get_receivers,
    async_subscribe_receiver,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    CONF_MODULATION,
    CONF_TIMINGS,
    DOMAIN,
    SUBENTRY_TYPE_COMMAND,
)

LEARN_TIMEOUT = 30

# Most receivers demodulate the signal and do not report the carrier.
# 38 kHz is the carrier that most consumer remotes use.
DEFAULT_MODULATION = 38000

NAME_SCHEMA = probatio.Schema({probatio.Required(CONF_NAME): TextSelector()})


class InfraredButtonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a device that sends commands through one emitter."""

    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types that this integration supports."""
        return {SUBENTRY_TYPE_COMMAND: CommandSubentryFlowHandler}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the name of the device and the emitter."""
        if not (emitters := async_get_emitters(self.hass)):
            return self.async_abort(reason="no_infrared_emitters")

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={CONF_INFRARED_ENTITY_ID: user_input[CONF_INFRARED_ENTITY_ID]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=NAME_SCHEMA.extend(
                {
                    probatio.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN, include_entities=emitters
                        )
                    ),
                }
            ),
        )


class CommandSubentryFlowHandler(ConfigSubentryFlow):
    """Learn a command from a remote."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._receiver_entity_id: str | None = None
        self._learn_task: asyncio.Task[InfraredReceivedSignal] | None = None
        self._signal: InfraredReceivedSignal | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select the receiver."""
        if not async_get_receivers(self.hass):
            return self.async_abort(reason="no_infrared_receivers")

        if user_input is not None:
            self._receiver_entity_id = user_input[CONF_INFRARED_RECEIVER_ENTITY_ID]
            return await self.async_step_learn()

        return self._async_show_user_form()

    async def async_step_learn(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Wait until the user presses a button on the remote."""
        if self._learn_task is None:
            self._signal = None
            # Start eagerly to subscribe before the progress step shows
            self._learn_task = self.hass.async_create_task(self._async_learn_signal())

        if not self._learn_task.done():
            return self.async_show_progress(
                step_id="learn",
                progress_action="wait_for_signal",
                progress_task=self._learn_task,
            )

        # On timeout, learn_done shows the receiver form again with an error
        with suppress(TimeoutError):
            self._signal = self._learn_task.result()
        self._learn_task = None

        return self.async_show_progress_done(next_step_id="learn_done")

    async def async_step_learn_done(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Continue to the name step, or retry when no signal came in."""
        if self._signal is None:
            return self._async_show_user_form({"base": "no_signal"})
        return await self.async_step_name()

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Name the learned command."""
        assert self._signal is not None
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_TIMINGS: self._signal.timings,
                    CONF_MODULATION: self._signal.modulation or DEFAULT_MODULATION,
                },
            )

        return self.async_show_form(step_id="name", data_schema=NAME_SCHEMA)

    @callback
    def _async_show_user_form(
        self, errors: dict[str, str] | None = None
    ) -> SubentryFlowResult:
        """Show the form to select the receiver."""
        schema = probatio.Schema(
            {
                probatio.Required(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(
                        domain=INFRARED_DOMAIN,
                        include_entities=async_get_receivers(self.hass),
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                schema, {CONF_INFRARED_RECEIVER_ENTITY_ID: self._receiver_entity_id}
            ),
            errors=errors,
        )

    async def _async_learn_signal(self) -> InfraredReceivedSignal:
        """Return the first signal that the receiver gets."""
        assert self._receiver_entity_id is not None
        future: asyncio.Future[InfraredReceivedSignal] = self.hass.loop.create_future()

        @callback
        def _async_on_signal(signal: InfraredReceivedSignal) -> None:
            if not future.done():
                future.set_result(signal)

        unsubscribe = async_subscribe_receiver(
            self.hass, self._receiver_entity_id, _async_on_signal
        )
        try:
            async with asyncio.timeout(LEARN_TIMEOUT):
                return await future
        finally:
            unsubscribe()
