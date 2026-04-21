"""Config flow for the Russound RNET integration."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from aiorussound import RussoundTcpConnectionHandler
from aiorussound.connection import RussoundSerialConnectionHandler
from aiorussound.rnet.client import RussoundRNETClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MODEL, CONF_PORT, CONF_TYPE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialSelector,
    TextSelector,
)

from .const import (
    CONF_CONTROLLERS,
    CONF_SOURCES,
    CONF_ZONES,
    DEFAULT_BAUDRATE,
    DOMAIN,
    RNET_EXCEPTIONS,
    RNET_MODELS,
    TYPE_SERIAL,
    TYPE_TCP,
)

TRANSPORT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE, default=TYPE_TCP): SelectSelector(
            SelectSelectorConfig(
                options=[TYPE_TCP, TYPE_SERIAL],
                translation_key="connection_type",
            )
        ),
    }
)

TCP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
    }
)

SERIAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialSelector(),
    }
)


async def _async_validate_connection(
    client: RussoundRNETClient,
) -> bool:
    """Validate a Russound RNET connection."""
    try:
        await client.connect()
        await client.get_all_zone_info(1, 1)
    except RNET_EXCEPTIONS:
        return False
    finally:
        with suppress(*RNET_EXCEPTIONS):
            await client.disconnect()
    return True


class RussoundRNETConfigFlow(ConfigFlow, domain=DOMAIN):
    """Russound RNET config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user — transport selection."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=TRANSPORT_SCHEMA,
            )

        self.data[CONF_TYPE] = user_input[CONF_TYPE]
        if user_input[CONF_TYPE] == TYPE_TCP:
            return await self.async_step_tcp()
        return await self.async_step_serial()

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle TCP configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            client = RussoundRNETClient(RussoundTcpConnectionHandler(host, port))
            if not await _async_validate_connection(client):
                errors["base"] = "cannot_connect"
            else:
                self.data[CONF_HOST] = host
                self.data[CONF_PORT] = port
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                return await self.async_step_model()

        return self.async_show_form(
            step_id="tcp", data_schema=TCP_SCHEMA, errors=errors
        )

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle serial configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device = user_input[CONF_DEVICE]

            client = RussoundRNETClient(
                RussoundSerialConnectionHandler(device, DEFAULT_BAUDRATE)
            )
            if not await _async_validate_connection(client):
                errors["base"] = "cannot_connect"
            else:
                self.data[CONF_DEVICE] = device
                await self.async_set_unique_id(device)
                self._abort_if_unique_id_configured()
                return await self.async_step_model()

        return self.async_show_form(
            step_id="serial", data_schema=SERIAL_SCHEMA, errors=errors
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle model selection and controller count."""
        if user_input is not None:
            self.data[CONF_MODEL] = user_input[CONF_MODEL]
            model = RNET_MODELS[self.data[CONF_MODEL]]
            self.data[CONF_CONTROLLERS] = int(
                user_input.get(CONF_CONTROLLERS, model.max_controllers)
            )
            return await self.async_step_sources()

        model_schema = vol.Schema(
            {
                vol.Required(CONF_MODEL): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=key, label=model.name)
                            for key, model in RNET_MODELS.items()
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="model",
                    )
                ),
                vol.Required(CONF_CONTROLLERS, default=1): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=max(m.max_controllers for m in RNET_MODELS.values()),
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="model", data_schema=model_schema)

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle source name configuration. Empty name = source excluded."""
        model = RNET_MODELS[self.data[CONF_MODEL]]

        if user_input is not None:
            # Only store non-empty source names
            sources = {
                str(i): name
                for i in range(1, model.max_sources + 1)
                if (name := user_input.get(f"source_{i}", "").strip())
            }
            self.data[CONF_SOURCES] = sources
            return await self.async_step_zones()

        # Pre-fill from YAML import data if available
        existing_sources = self.data.get(CONF_SOURCES, {})
        source_schema = vol.Schema(
            {
                vol.Optional(
                    f"source_{i}",
                    default=existing_sources.get(str(i), ""),
                ): TextSelector()
                for i in range(1, model.max_sources + 1)
            }
        )

        return self.async_show_form(step_id="sources", data_schema=source_schema)

    async def async_step_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle zone name configuration. Empty name = zone excluded."""
        model = RNET_MODELS[self.data[CONF_MODEL]]
        num_controllers = self.data[CONF_CONTROLLERS]

        if user_input is not None:
            # Only store non-empty zone names; key = "controller_zone" e.g. "1_1"
            zones = {
                f"{c}_{z}": name
                for c in range(1, num_controllers + 1)
                for z in range(1, model.max_zones + 1)
                if (name := user_input.get(f"zone_{c}_{z}", "").strip())
            }
            self.data[CONF_ZONES] = zones
            return self.async_create_entry(
                title=model.name,
                data=self.data,
            )

        # Pre-fill from YAML import data if available
        existing_zones = self.data.get(CONF_ZONES, {})
        zone_schema = vol.Schema(
            {
                vol.Optional(
                    f"zone_{c}_{z}",
                    default=existing_zones.get(f"{c}_{z}", ""),
                ): TextSelector()
                for c in range(1, num_controllers + 1)
                for z in range(1, model.max_zones + 1)
            }
        )

        return self.async_show_form(step_id="zones", data_schema=zone_schema)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import config from YAML (called by repair flow with complete data)."""
        host = import_data.get(CONF_HOST, "")
        port = import_data.get(CONF_PORT, 0)

        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()

        model_key = import_data[CONF_MODEL]
        model = RNET_MODELS[model_key]
        return self.async_create_entry(
            title=model.name,
            data=import_data,
        )
