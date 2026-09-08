"""Config flow for Envisalink."""

import logging
from typing import Any, override

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
from homeassistant.const import CONF_CODE, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, selector

from . import InvalidAuth, LoginTimeout, async_connect_panel, disconnect_panel
from .const import (
    CONF_EVL_PORT,
    CONF_EVL_VERSION,
    CONF_PANEL_TYPE,
    CONF_PANIC,
    CONF_PARTITION_NUMBER,
    CONF_PARTITIONNAME,
    CONF_PARTITIONS,
    CONF_PASS,
    CONF_USERNAME,
    CONF_ZONE_NUMBER,
    CONF_ZONENAME,
    CONF_ZONES,
    CONF_ZONETYPE,
    DEFAULT_EVL_VERSION,
    DEFAULT_PANIC,
    DEFAULT_PORT,
    DEFAULT_ZONETYPE,
    DOMAIN,
    EVL_VERSIONS,
    MAX_PARTITIONS,
    MAX_ZONES_BY_EVL_VERSION,
    PANEL_TYPE_DSC,
    PANEL_TYPE_HONEYWELL,
    PANIC_TYPES,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_ZONE,
)

_LOGGER = logging.getLogger(__name__)

CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_EVL_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_PANEL_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=PANEL_TYPE_HONEYWELL, label="Honeywell"
                    ),
                    selector.SelectOptionDict(value=PANEL_TYPE_DSC, label="DSC"),
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_EVL_VERSION, default=DEFAULT_EVL_VERSION): vol.All(
            vol.Coerce(str),
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[str(version) for version in EVL_VERSIONS],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="evl_version",
                )
            ),
            vol.Coerce(int),
        ),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASS): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)

CODE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(CONF_PANIC, default=DEFAULT_PANIC): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=PANIC_TYPES,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONENAME): cv.string,
        vol.Required(CONF_ZONETYPE, default=DEFAULT_ZONETYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[cls.value for cls in BinarySensorDeviceClass],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="binary_sensor_device_class",
                sort=True,
            ),
        ),
    }
)

PARTITION_SCHEMA = vol.Schema({vol.Required(CONF_PARTITIONNAME): cv.string})


async def _async_test_connection(
    hass: HomeAssistant,
    host: str,
    port: int,
    panel_type: str,
    version: int,
    user_name: str,
    password: str,
) -> str | None:
    """Attempt a connection to the panel and return an error code, if any."""
    try:
        controller, login_succeeded = await async_connect_panel(
            hass, host, port, panel_type, version, user_name, password
        )
    except InvalidAuth:
        return "invalid_auth"
    except LoginTimeout:
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error while connecting to %s:%s", host, port)
        return "unknown"

    disconnect_panel(controller)
    return None if login_succeeded else "cannot_connect"


class EnvisalinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Envisalink."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self.connection_data: dict[str, Any] = {}

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            SUBENTRY_TYPE_ZONE: ZoneSubentryFlowHandler,
            SUBENTRY_TYPE_PARTITION: PartitionSubentryFlowHandler,
        }

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> EnvisalinkOptionsFlow:
        """Create the options flow."""
        return EnvisalinkOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await _async_test_connection(
                self.hass,
                user_input[CONF_HOST],
                user_input[CONF_EVL_PORT],
                user_input[CONF_PANEL_TYPE],
                user_input[CONF_EVL_VERSION],
                user_input[CONF_USERNAME],
                user_input[CONF_PASS],
            )
            if error:
                errors["base"] = error
            else:
                self.connection_data = user_input
                return await self.async_step_code()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CONNECTION_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the alarm code and panic type step."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.connection_data[CONF_HOST],
                data=self.connection_data,
                options=user_input,
            )

        return self.async_show_form(step_id="code", data_schema=CODE_SCHEMA)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import Envisalink configuration from configuration.yaml."""
        port = import_data.get(CONF_EVL_PORT, DEFAULT_PORT)
        version = import_data.get(CONF_EVL_VERSION, DEFAULT_EVL_VERSION)

        max_zone_number = MAX_ZONES_BY_EVL_VERSION[version]
        for zone_number in import_data.get(CONF_ZONES, {}):
            if not 1 <= zone_number <= max_zone_number:
                return self.async_abort(
                    reason="invalid_zone_number",
                    description_placeholders={
                        "number": str(zone_number),
                        "max": str(max_zone_number),
                    },
                )
        for partition_number in import_data.get(CONF_PARTITIONS, {}):
            if not 1 <= partition_number <= MAX_PARTITIONS:
                return self.async_abort(
                    reason="invalid_partition_number",
                    description_placeholders={
                        "number": str(partition_number),
                        "max": str(MAX_PARTITIONS),
                    },
                )

        error = await _async_test_connection(
            self.hass,
            import_data[CONF_HOST],
            port,
            import_data[CONF_PANEL_TYPE],
            version,
            import_data[CONF_USERNAME],
            import_data[CONF_PASS],
        )
        if error:
            return self.async_abort(reason=error)

        subentries: list[ConfigSubentryData] = []
        for zone_number, zone_config in import_data.get(CONF_ZONES, {}).items():
            zone_name = zone_config[CONF_ZONENAME]
            subentries.append(
                {
                    "subentry_type": SUBENTRY_TYPE_ZONE,
                    "title": f"{zone_name} ({zone_number})",
                    "unique_id": f"{SUBENTRY_TYPE_ZONE}_{zone_number}",
                    "data": {
                        CONF_ZONE_NUMBER: zone_number,
                        CONF_ZONENAME: zone_name,
                        CONF_ZONETYPE: zone_config.get(CONF_ZONETYPE, DEFAULT_ZONETYPE),
                    },
                }
            )
        for partition_number, partition_config in import_data.get(
            CONF_PARTITIONS, {}
        ).items():
            partition_name = partition_config[CONF_PARTITIONNAME]
            subentries.append(
                {
                    "subentry_type": SUBENTRY_TYPE_PARTITION,
                    "title": f"{partition_name} ({partition_number})",
                    "unique_id": f"{SUBENTRY_TYPE_PARTITION}_{partition_number}",
                    "data": {
                        CONF_PARTITION_NUMBER: partition_number,
                        CONF_PARTITIONNAME: partition_name,
                    },
                }
            )

        return self.async_create_entry(
            title=import_data[CONF_HOST],
            data={
                CONF_HOST: import_data[CONF_HOST],
                CONF_EVL_PORT: port,
                CONF_PANEL_TYPE: import_data[CONF_PANEL_TYPE],
                CONF_EVL_VERSION: version,
                CONF_USERNAME: import_data[CONF_USERNAME],
                CONF_PASS: import_data[CONF_PASS],
            },
            options={
                CONF_CODE: import_data.get(CONF_CODE),
                CONF_PANIC: import_data.get(CONF_PANIC, DEFAULT_PANIC),
            },
            subentries=subentries,
        )


class EnvisalinkOptionsFlow(OptionsFlow):
    """Handle an Envisalink options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                CODE_SCHEMA, self.config_entry.options
            ),
        )


class ZoneSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for adding and modifying a zone."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new zone."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"{SUBENTRY_TYPE_ZONE}_{user_input[CONF_ZONE_NUMBER]}"

            for existing_subentry in self._get_entry().subentries.values():
                if existing_subentry.unique_id == unique_id:
                    errors[CONF_ZONE_NUMBER] = "already_configured"

            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_ZONENAME]} ({user_input[CONF_ZONE_NUMBER]})",
                    data=user_input,
                    unique_id=unique_id,
                )

        max_zone_number = MAX_ZONES_BY_EVL_VERSION[
            self._get_entry().data[CONF_EVL_VERSION]
        ]
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZONE_NUMBER): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=max_zone_number)
                    ),
                }
            ).extend(ZONE_SCHEMA.schema),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure an existing zone."""
        subconfig_entry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subconfig_entry,
                title=(
                    f"{user_input[CONF_ZONENAME]}"
                    f" ({subconfig_entry.data[CONF_ZONE_NUMBER]})"
                ),
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                ZONE_SCHEMA, subconfig_entry.data
            ),
            description_placeholders={
                CONF_ZONE_NUMBER: str(subconfig_entry.data[CONF_ZONE_NUMBER])
            },
        )


class PartitionSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for adding and modifying a partition."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new partition."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"{SUBENTRY_TYPE_PARTITION}_{user_input[CONF_PARTITION_NUMBER]}"

            for existing_subentry in self._get_entry().subentries.values():
                if existing_subentry.unique_id == unique_id:
                    errors[CONF_PARTITION_NUMBER] = "already_configured"

            if not errors:
                return self.async_create_entry(
                    title=(
                        f"{user_input[CONF_PARTITIONNAME]}"
                        f" ({user_input[CONF_PARTITION_NUMBER]})"
                    ),
                    data=user_input,
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PARTITION_NUMBER): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=MAX_PARTITIONS)
                    ),
                }
            ).extend(PARTITION_SCHEMA.schema),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure an existing partition."""
        subconfig_entry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subconfig_entry,
                title=(
                    f"{user_input[CONF_PARTITIONNAME]}"
                    f" ({subconfig_entry.data[CONF_PARTITION_NUMBER]})"
                ),
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                PARTITION_SCHEMA, subconfig_entry.data
            ),
            description_placeholders={
                CONF_PARTITION_NUMBER: str(subconfig_entry.data[CONF_PARTITION_NUMBER])
            },
        )
