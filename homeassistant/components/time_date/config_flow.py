"""Adds config flow for Time & Date integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.setup import async_prepare_setup_platform

from .const import CONF_DISPLAY_OPTIONS, DOMAIN, OPTION_TYPES
from .sensor import TimeDateSensor

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DISPLAY_OPTIONS): SelectSelector(
            SelectSelectorConfig(
                options=OPTION_TYPES,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="display_options",
            )
        ),
    }
)


async def validate_input(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate rest setup."""
    hass = handler.parent_handler.hass
    if hass.config.time_zone is None:
        raise SchemaFlowError("timezone_not_exist")
    return user_input


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=USER_SCHEMA,
        preview=DOMAIN,
        validate_user_input=validate_input,
    )
}


class TimeDateConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Time & Date."""

    config_flow = CONFIG_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return f"Time & Date {options[CONF_DISPLAY_OPTIONS]}"

    def async_config_flow_finished(self, options: Mapping[str, Any]) -> None:
        """Abort if instance already exist."""
        self._async_abort_entries_match(dict(options))

    @staticmethod
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up preview WS API."""
        websocket_api.async_register_command(hass, ws_start_preview)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "time_date/start_preview",
        vol.Required("flow_id"): str,
        vol.Required("flow_type"): vol.Any("config_flow"),
        vol.Required("user_input"): dict,
    }
)
@websocket_api.async_response
async def ws_start_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate a preview."""
    validated = USER_SCHEMA(msg["user_input"])

    # Create an EntityPlatform, needed for name translations
    platform = await async_prepare_setup_platform(hass, {}, SENSOR_DOMAIN, DOMAIN)
    entity_platform = EntityPlatform(
        hass=hass,
        logger=_LOGGER,
        domain=SENSOR_DOMAIN,
        platform_name=DOMAIN,
        platform=platform,
        scan_interval=timedelta(seconds=3600),
        entity_namespace=None,
    )
    await entity_platform.async_load_translations()

    @callback
    def async_preview_updated(state: str, attributes: Mapping[str, Any]) -> None:
        """Forward config entry state events to websocket."""
        connection.send_message(
            websocket_api.event_message(
                msg["id"], {"attributes": attributes, "state": state}
            )
        )

    preview_entity = TimeDateSensor(validated[CONF_DISPLAY_OPTIONS])
    preview_entity.hass = hass
    preview_entity.platform = entity_platform

    connection.send_result(msg["id"])
    connection.subscriptions[msg["id"]] = preview_entity.async_start_preview(
        async_preview_updated
    )
