"""Config flow for the NX584 integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
import requests

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_ENTITY_NAMESPACE,
    CONF_HOST,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PORT,
)

from . import create_client
from .const import (
    CONF_ENTITY_NAMESPACES,
    CONF_EXCLUDE_ZONES,
    CONF_ZONE_TYPES,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST, default=DEFAULT_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
    }
)


def _with_entity_namespace(
    data: Mapping[str, Any], platform: str, namespace: str | None
) -> dict[str, Any]:
    """Return the entry data with the entity namespace of one platform replaced."""
    entry_data = {k: v for k, v in data.items() if k != CONF_ENTITY_NAMESPACES}
    namespaces = {**data.get(CONF_ENTITY_NAMESPACES, {}), platform: namespace}
    if namespaces := {p: ns for p, ns in namespaces.items() if ns is not None}:
        entry_data[CONF_ENTITY_NAMESPACES] = namespaces
    return entry_data


class NX584ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NX584."""

    VERSION = 1

    async def _async_validate(self, host: str, port: int) -> None:
        """Connect to the server; raise if it cannot be reached."""
        client = create_client(host, port)
        await self.hass.async_add_executor_job(client.list_zones)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host: str = user_input[CONF_HOST]
            port: int = user_input[CONF_PORT]
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                await self._async_validate(host, port)
            except requests.exceptions.ConnectionError, requests.exceptions.Timeout:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=DEFAULT_NAME, data={CONF_HOST: host, CONF_PORT: port}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import the YAML configuration of one platform."""
        platform: str = import_data[CONF_PLATFORM]
        host: str = import_data[CONF_HOST]
        port: int = import_data[CONF_PORT]
        namespace: str | None = import_data.get(CONF_ENTITY_NAMESPACE)
        data: dict[str, Any] = {CONF_HOST: host, CONF_PORT: port}
        if CONF_NAME in import_data:
            data[CONF_NAME] = import_data[CONF_NAME]
        options: dict[str, Any] = {}
        if CONF_EXCLUDE_ZONES in import_data:
            options[CONF_EXCLUDE_ZONES] = list(import_data[CONF_EXCLUDE_ZONES])
        if CONF_ZONE_TYPES in import_data:
            # Entry options are stored as JSON, so zone numbers become strings.
            options[CONF_ZONE_TYPES] = {
                str(zone): str(zone_type)
                for zone, zone_type in import_data[CONF_ZONE_TYPES].items()
            }

        unique_id = f"{host}:{port}"
        await self.async_set_unique_id(unique_id)
        if entry := self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, unique_id
        ):
            # Each platform owns its keys; the other platform's keys are kept.
            return self.async_update_reload_and_abort(
                entry,
                data=_with_entity_namespace(
                    {**entry.data, **data}, platform, namespace
                ),
                options={**entry.options, **options},
                reason="already_configured",
                reload_even_if_entry_is_unchanged=False,
            )

        try:
            await self._async_validate(host, port)
        except requests.exceptions.ConnectionError, requests.exceptions.Timeout:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=data.get(CONF_NAME, DEFAULT_NAME),
            data=_with_entity_namespace(data, platform, namespace),
            options=options,
        )
