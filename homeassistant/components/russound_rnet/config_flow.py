"""Config flow for the Russound RNET integration."""

from __future__ import annotations

from contextlib import suppress
import logging
from typing import Any

from aiorussound import RussoundTcpConnectionHandler
from aiorussound.connection import RussoundSerialConnectionHandler
from aiorussound.rnet.client import RussoundRNETClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialSelector,
    TextSelector,
)

from .const import (
    CONF_BAUDRATE,
    CONF_MODEL,
    CONF_SOURCES,
    CONF_ZONES,
    DEFAULT_BAUDRATE,
    DOMAIN,
    RNET_EXCEPTIONS,
    RNET_MODELS,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .coordinator import RussoundRNETConfigEntry
from .issue import deprecate_yaml_issue

_LOGGER = logging.getLogger(__name__)

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
        vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.All(
            vol.Coerce(int),
            vol.Range(min=1),
        ),
    }
)

MODEL_SCHEMA = vol.Schema(
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


def _infer_model_from_zones(zone_ids: list[int]) -> str:
    """Infer model key from YAML zone IDs."""
    max_zone = max(zone_ids) if zone_ids else 6
    if max_zone <= 4:
        return "cas44"
    if max_zone <= 6:
        return "caa66"
    return "mca-c5"


class RussoundRNETConfigFlow(ConfigFlow, domain=DOMAIN):
    """Russound RNET config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: RussoundRNETConfigEntry,
    ) -> RussoundRNETOptionsFlow:
        """Return the options flow handler."""
        return RussoundRNETOptionsFlow()

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

            self._async_abort_entries_match(
                {CONF_TYPE: TYPE_TCP, CONF_HOST: host, CONF_PORT: port}
            )

            client = RussoundRNETClient(RussoundTcpConnectionHandler(host, port))
            if not await _async_validate_connection(client):
                errors["base"] = "cannot_connect"
            else:
                self.data[CONF_HOST] = host
                self.data[CONF_PORT] = port
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
            baudrate = user_input.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)

            self._async_abort_entries_match(
                {CONF_TYPE: TYPE_SERIAL, CONF_DEVICE: device}
            )

            client = RussoundRNETClient(
                RussoundSerialConnectionHandler(device, baudrate)
            )
            if not await _async_validate_connection(client):
                errors["base"] = "cannot_connect"
            else:
                self.data[CONF_DEVICE] = device
                self.data[CONF_BAUDRATE] = baudrate
                return await self.async_step_model()

        return self.async_show_form(
            step_id="serial", data_schema=SERIAL_SCHEMA, errors=errors
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle model selection."""
        if user_input is not None:
            self.data[CONF_MODEL] = user_input[CONF_MODEL]
            return await self.async_step_sources()

        return self.async_show_form(step_id="model", data_schema=MODEL_SCHEMA)

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

        source_schema = vol.Schema(
            {
                vol.Optional(f"source_{i}", default=""): TextSelector()
                for i in range(1, model.max_sources + 1)
            }
        )

        return self.async_show_form(step_id="sources", data_schema=source_schema)

    async def async_step_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle zone name configuration. Empty name = zone excluded."""
        model = RNET_MODELS[self.data[CONF_MODEL]]

        if user_input is not None:
            # Only store non-empty zone names; key = "controller_zone" e.g. "1_1"
            zones = {
                f"{c}_{z}": name
                for c in range(1, model.max_controllers + 1)
                for z in range(1, model.max_zones + 1)
                if (name := user_input.get(f"zone_{c}_{z}", "").strip())
            }
            self.data[CONF_ZONES] = zones
            return self.async_create_entry(
                title=model.name,
                data=self.data,
            )

        zone_schema = vol.Schema(
            {
                vol.Optional(f"zone_{c}_{z}", default=""): TextSelector()
                for c in range(1, model.max_controllers + 1)
                for z in range(1, model.max_zones + 1)
            }
        )

        return self.async_show_form(step_id="zones", data_schema=zone_schema)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import config from YAML."""
        host = import_data.get(CONF_HOST, "")
        port = import_data.get(CONF_PORT, 0)

        self._async_abort_entries_match(
            {CONF_TYPE: TYPE_TCP, CONF_HOST: host, CONF_PORT: port}
        )

        # Build source names from YAML config (only named sources)
        yaml_sources = import_data.get("sources", [])
        sources = {
            str(i + 1): src.get(CONF_NAME, "")
            for i, src in enumerate(yaml_sources)
            if src.get(CONF_NAME, "").strip()
        }

        # Infer model from zone configuration
        yaml_zones = import_data.get("zones", {})
        zone_ids = list(yaml_zones.keys()) if yaml_zones else []
        model_key = _infer_model_from_zones(zone_ids)

        # Preserve zone names from YAML; old YAML used flat zone IDs
        # mapped as controller = ceil(id/6), zone = ((id-1) % 6) + 1
        zones = {}
        for zone_id, zone_data in yaml_zones.items():
            controller_id = (zone_id - 1) // 6 + 1
            local_zone_id = (zone_id - 1) % 6 + 1
            name = zone_data.get(CONF_NAME, "").strip()
            if name:
                zones[f"{controller_id}_{local_zone_id}"] = name

        data = {
            CONF_TYPE: TYPE_TCP,
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_MODEL: model_key,
            CONF_SOURCES: sources,
            CONF_ZONES: zones,
        }

        # Validate connection
        client = RussoundRNETClient(RussoundTcpConnectionHandler(host, port))
        if not await _async_validate_connection(client):
            deprecate_yaml_issue(self.hass, import_success=False)
            return self.async_abort(reason="cannot_connect")

        deprecate_yaml_issue(self.hass, import_success=True)
        return self.async_create_entry(
            title=RNET_MODELS[model_key].name,
            data=data,
        )


class RussoundRNETOptionsFlow(OptionsFlow):
    """Options flow for Russound RNET — edit source names."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow init."""
        entry = self.config_entry
        model_key = entry.data.get(CONF_MODEL, "caa66")
        model = RNET_MODELS[model_key]
        current_sources = entry.data.get(CONF_SOURCES, {})

        if user_input is not None:
            # Only store non-empty source names
            new_sources = {
                str(i): name
                for i in range(1, model.max_sources + 1)
                if (name := user_input.get(f"source_{i}", "").strip())
            }
            new_data = {**entry.data, CONF_SOURCES: new_sources}
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_create_entry(data={})

        source_schema = vol.Schema(
            {
                vol.Optional(
                    f"source_{i}",
                    default=current_sources.get(str(i), ""),
                ): TextSelector()
                for i in range(1, model.max_sources + 1)
            }
        )

        return self.async_show_form(step_id="init", data_schema=source_schema)
