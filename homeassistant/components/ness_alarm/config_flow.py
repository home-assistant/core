"""Config flow for Ness Alarm integration."""

from __future__ import annotations

import asyncio
import logging
from types import MappingProxyType
from typing import Any

from nessclient import Client
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_INFER_ARMING_STATE,
    CONF_SHOW_HOME_MODE,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    CONNECTION_TIMEOUT,
    DEFAULT_INFER_ARMING_STATE,
    DEFAULT_PORT,
    DEFAULT_ZONE_TYPE,
    DOMAIN,
    POST_CONNECTION_DELAY,
    SUBENTRY_TYPE_ZONE,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_INFER_ARMING_STATE, default=DEFAULT_INFER_ARMING_STATE): bool,
    }
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE, default=DEFAULT_ZONE_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[cls.value for cls in BinarySensorDeviceClass],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="binary_sensor_device_class",
                sort=True,
            ),
        ),
    }
)


class NessAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ness Alarm."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            SUBENTRY_TYPE_ZONE: ZoneSubentryFlowHandler,
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return NessAlarmOptionsFlowHandler()

    async def _test_connection(self, host: str, port: int) -> None:
        """Test connection to the alarm panel.

        Raises OSError on connection failure.
        """
        client = Client(host=host, port=port)
        try:
            await asyncio.wait_for(client.update(), timeout=CONNECTION_TIMEOUT)
        except TimeoutError as err:
            raise OSError(f"Timed out connecting to {host}:{port}") from err
        finally:
            await client.close()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Check if already configured
            self._async_abort_entries_match({CONF_HOST: host})

            # Test connection to the alarm panel
            try:
                await self._test_connection(host, port)
            except OSError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to %s:%s", host, port)
                errors["base"] = "unknown"

            if not errors:
                # Brief delay to ensure the panel releases the test connection
                await asyncio.sleep(POST_CONNECTION_DELAY)
                return self.async_create_entry(
                    title=f"Ness Alarm {host}:{port}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import YAML configuration."""
        host = import_data[CONF_HOST]
        port = import_data[CONF_PORT]

        # Check if already configured
        self._async_abort_entries_match({CONF_HOST: host})

        # Test connection to the alarm panel
        try:
            await self._test_connection(host, port)
        except OSError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception(
                "Unexpected error connecting to %s:%s during import", host, port
            )
            return self.async_abort(reason="unknown")

        # Brief delay to ensure the panel releases the test connection
        await asyncio.sleep(POST_CONNECTION_DELAY)

        # Prepare subentries for zones
        subentries: list[ConfigSubentryData] = []
        zones = import_data.get(CONF_ZONES, [])

        for zone_config in zones:
            zone_id = zone_config[CONF_ZONE_ID]
            zone_name = zone_config.get(CONF_ZONE_NAME)
            zone_type = zone_config.get(CONF_ZONE_TYPE, DEFAULT_ZONE_TYPE)

            # Subentry title is always "Zone {zone_id}"
            title = f"Zone {zone_id}"

            # Build subentry data
            subentry_data = {
                CONF_ZONE_NUMBER: zone_id,
                CONF_TYPE: zone_type,
            }
            # Include zone name in data if provided (for device naming)
            if zone_name:
                subentry_data[CONF_ZONE_NAME] = zone_name

            subentries.append(
                {
                    "subentry_type": SUBENTRY_TYPE_ZONE,
                    "title": title,
                    "unique_id": f"{SUBENTRY_TYPE_ZONE}_{zone_id}",
                    "data": MappingProxyType(subentry_data),
                }
            )

        return self.async_create_entry(
            title=f"Ness Alarm {host}:{port}",
            data={
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_INFER_ARMING_STATE: import_data.get(
                    CONF_INFER_ARMING_STATE, DEFAULT_INFER_ARMING_STATE
                ),
            },
            subentries=subentries,
        )


class NessAlarmOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Ness Alarm."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_SHOW_HOME_MODE, default=True): bool,
                    }
                ),
                self.config_entry.options,
            ),
        )


class ZoneSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a zone."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add new zone."""
        errors: dict[str, str] = {}

        if user_input is not None:
            zone_number = int(user_input[CONF_ZONE_NUMBER])
            unique_id = f"{SUBENTRY_TYPE_ZONE}_{zone_number}"

            # Check if zone already exists
            for existing_subentry in self._get_entry().subentries.values():
                if existing_subentry.unique_id == unique_id:
                    errors[CONF_ZONE_NUMBER] = "already_configured"

            if not errors:
                # Store zone_number as int in data
                user_input[CONF_ZONE_NUMBER] = zone_number
                return self.async_create_entry(
                    title=f"Zone {zone_number}",
                    data=user_input,
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZONE_NUMBER): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=32,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ).extend(ZONE_SCHEMA.schema),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure existing zone."""
        subconfig_entry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subconfig_entry,
                title=f"Zone {subconfig_entry.data[CONF_ZONE_NUMBER]}",
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                ZONE_SCHEMA,
                subconfig_entry.data,
            ),
            description_placeholders={
                CONF_ZONE_NUMBER: str(subconfig_entry.data[CONF_ZONE_NUMBER])
            },
        )
