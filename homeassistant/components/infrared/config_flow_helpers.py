"""Config flow helpers for integrations that consume infrared emitters/receivers."""

from abc import ABCMeta, abstractmethod
from collections.abc import Mapping
from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import DOMAIN
from .helpers import async_get_emitters, async_get_receivers


class InfraredConsumerConfigFlow(ConfigFlow, metaclass=ABCMeta):
    """Base config flow for integrations that consume infrared entities.

    Subclasses need the `no_infrared_emitters` and `already_configured` abort
    translations.
    """

    INFRARED_EMITTER_KEY: str
    INFRARED_RECEIVER_KEY: str | None = None

    @abstractmethod
    async def _async_infrared_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return the title of a new entry."""

    @callback
    def _async_infrared_schema(self) -> probatio.Schema:
        """Return the schema of the user step."""
        return probatio.Schema(self._async_infrared_entity_fields())

    @callback
    def _async_infrared_match_dict(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Return the data an entry must also match to count as a duplicate."""
        return {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        self._async_abort_if_no_infrared_emitters()

        if user_input is not None:
            self._async_abort_infrared_entities_match(
                user_input, self._async_infrared_match_dict(user_input)
            )
            return self.async_create_entry(
                title=await self._async_infrared_entry_title(user_input),
                data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=self._async_infrared_schema()
        )

    @callback
    def _async_infrared_entity_fields(self) -> dict[probatio.Marker, EntitySelector]:
        """Return the schema fields to select the infrared entities."""
        fields: dict[probatio.Marker, EntitySelector] = {
            probatio.Required(self.INFRARED_EMITTER_KEY): EntitySelector(
                EntitySelectorConfig(
                    domain=DOMAIN, include_entities=async_get_emitters(self.hass)
                )
            ),
        }
        if self.INFRARED_RECEIVER_KEY is not None:
            fields[probatio.Optional(self.INFRARED_RECEIVER_KEY)] = EntitySelector(
                EntitySelectorConfig(
                    domain=DOMAIN, include_entities=async_get_receivers(self.hass)
                )
            )
        return fields

    @callback
    def _async_abort_if_no_infrared_emitters(self) -> None:
        """Abort the flow if there are no infrared emitters."""
        if not async_get_emitters(self.hass):
            raise AbortFlow("no_infrared_emitters")

    @callback
    def _async_abort_infrared_entities_match(
        self,
        user_input: Mapping[str, Any],
        match_dict: dict[str, Any] | None = None,
    ) -> None:
        """Abort if an entry already uses one of the selected infrared entities.

        Each selected entity is matched on its own, together with `match_dict`.
        """
        match_dict = match_dict or {}
        self._async_abort_entries_match(
            {
                **match_dict,
                self.INFRARED_EMITTER_KEY: user_input[self.INFRARED_EMITTER_KEY],
            }
        )
        if self.INFRARED_RECEIVER_KEY is not None and (
            receiver_id := user_input.get(self.INFRARED_RECEIVER_KEY)
        ):
            self._async_abort_entries_match(
                {**match_dict, self.INFRARED_RECEIVER_KEY: receiver_id}
            )

    @callback
    def _async_infrared_entity_name(self, entity_id: str) -> str:
        """Return the name of an infrared entity, for use in the entry title."""
        if (entry := er.async_get(self.hass).async_get(entity_id)) is None:
            return entity_id
        return er.async_get_full_entity_name(self.hass, entry) or entity_id


class InfraredConsumerReconfigureConfigFlow(InfraredConsumerConfigFlow):
    """Base config flow for infrared consumers that support reconfiguration.

    Subclasses also need the `reconfigure` step translations.
    """

    @callback
    def _async_infrared_reconfigure_schema(self) -> probatio.Schema:
        """Return the schema of the reconfigure step."""
        return probatio.Schema(self._async_infrared_entity_fields())

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the entry."""
        entry = self._get_reconfigure_entry()
        self._async_abort_if_no_infrared_emitters()
        schema = self._async_infrared_reconfigure_schema()

        if user_input is not None:
            # Keep the data the form does not show, and drop cleared optional fields.
            data = {
                key: value
                for key, value in entry.data.items()
                if key not in schema.schema
            } | user_input
            self._async_abort_infrared_entities_match(
                data, self._async_infrared_match_dict(data)
            )
            return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, entry.data),
        )
