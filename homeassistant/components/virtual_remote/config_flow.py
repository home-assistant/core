"""Config flow for the Virtual Remote integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)
from .options_flow import VirtualRemoteOptionsFlow

_REMOTE_ID_RE = re.compile(r"[^a-z0-9_]+")


class VirtualRemoteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Virtual Remote."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> VirtualRemoteOptionsFlow:
        """Create the options flow."""
        return VirtualRemoteOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        available_infrared_entities = _available_infrared_entities(self.hass)

        if not available_infrared_entities:
            return self.async_abort(reason="no_available_infrared_entities")

        if user_input is not None:
            name = str(user_input[CONF_REMOTE_NAME]).strip()
            infrared_entity_id = str(user_input[CONF_INFRARED_ENTITY_ID]).strip()
            remote_id = _slugify_remote_id(name)

            if not name:
                errors[CONF_REMOTE_NAME] = "remote_name_required"

            if infrared_entity_id not in available_infrared_entities:
                errors[CONF_INFRARED_ENTITY_ID] = "infrared_entity_unavailable"

            if not errors:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Virtual Remote",
                    data={},
                    options={
                        CONF_VIRTUAL_REMOTES: [
                            {
                                CONF_REMOTE_ID: remote_id,
                                CONF_REMOTE_NAME: name,
                                CONF_INFRARED_ENTITY_ID: infrared_entity_id,
                            }
                        ],
                    },
                )

        remote_name_default = (
            str(user_input.get(CONF_REMOTE_NAME, "")) if user_input else ""
        )
        infrared_entity_default = (
            str(user_input.get(CONF_INFRARED_ENTITY_ID, "")) if user_input else ""
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REMOTE_NAME,
                        default=remote_name_default,
                    ): str,
                    _infrared_entity_field(
                        infrared_entity_default,
                        available_infrared_entities,
                    ): _infrared_entity_selector(available_infrared_entities),
                }
            ),
            errors=errors,
        )


def _available_infrared_entities(
    hass,
) -> dict[str, selector.SelectOptionDict]:
    """Return available infrared entities.

    Multiple virtual remotes may use the same infrared transmitter because one
    physical IR output can control multiple appliances, for example through
    dual emitters or a blaster.
    """
    registry = er.async_get(hass)
    options: dict[str, selector.SelectOptionDict] = {}

    for registry_entry in registry.entities.values():
        if registry_entry.domain != "infrared":
            continue

        entity_id = registry_entry.entity_id
        label = (
            registry_entry.name
            or registry_entry.original_name
            or registry_entry.entity_id
        )
        options[entity_id] = selector.SelectOptionDict(
            value=entity_id,
            label=label,
        )

    return dict(sorted(options.items()))


def _infrared_entity_selector(
    available_infrared_entities: dict[str, selector.SelectOptionDict],
) -> selector.SelectSelector:
    """Return an infrared entity selector."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(available_infrared_entities.values()),
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _infrared_entity_field(
    default_entity_id: str,
    available_infrared_entities: dict[str, selector.SelectOptionDict],
) -> vol.Required:
    """Return a required infrared entity field with a valid default if possible."""
    if default_entity_id in available_infrared_entities:
        return vol.Required(
            CONF_INFRARED_ENTITY_ID,
            default=default_entity_id,
        )
    return vol.Required(CONF_INFRARED_ENTITY_ID)


def _slugify_remote_id(name: str) -> str:
    """Create a stable id from a remote name."""
    value = name.strip().casefold().replace(" ", "_")
    value = _REMOTE_ID_RE.sub("_", value)
    value = value.strip("_")
    return value or "remote"
