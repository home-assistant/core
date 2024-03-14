"""The Things Network's integration config flow."""

from collections import OrderedDict
from collections.abc import Mapping
import copy
import logging
from typing import Any

from ttn_client import TTNAuthError, TTNClient
import voluptuous as vol

from homeassistant.config_entries import (
    HANDLERS,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_ACCESS_KEY,
    CONF_APP_ID,
    CONF_HOSTNAME,
    DEFAULT_API_REFRESH_PERIOD_S,
    DEFAULT_FIRST_FETCH_LAST_H,
    DOMAIN,
    OPTIONS_DEVICE_NAME,
    OPTIONS_FIELD_CONTEXT_RECENT_TIME_S,
    OPTIONS_FIELD_DEVICE_CLASS,
    OPTIONS_FIELD_DEVICE_SCOPE,
    OPTIONS_FIELD_DEVICE_SCOPE_GLOBAL,
    OPTIONS_FIELD_ENTITY_TYPE,
    OPTIONS_FIELD_ENTITY_TYPE_AUTO,
    OPTIONS_FIELD_ENTITY_TYPE_BINARY_SENSOR,
    OPTIONS_FIELD_ENTITY_TYPE_DEVICE_TRACKER,
    OPTIONS_FIELD_ENTITY_TYPE_SENSOR,
    OPTIONS_FIELD_ICON,
    OPTIONS_FIELD_NAME,
    OPTIONS_FIELD_PICTURE,
    OPTIONS_FIELD_SUPPORTED_FEATURES,
    OPTIONS_FIELD_UNIT_MEASUREMENT,
    OPTIONS_MENU_EDIT_DEVICES,
    OPTIONS_MENU_EDIT_FIELDS,
    OPTIONS_MENU_EDIT_INTEGRATION,
    OPTIONS_MENU_INTEGRATION_FIRST_FETCH_TIME_H,
    OPTIONS_MENU_INTEGRATION_REFRESH_TIME_S,
    OPTIONS_SELECTED_DEVICE,
    OPTIONS_SELECTED_FIELD,
    OPTIONS_SELECTED_MENU,
    TTN_API_HOSTNAME,
)
from .entry_settings import TTN_EntrySettings

_LOGGER = logging.getLogger(__name__)


@HANDLERS.register(DOMAIN)
class TTNFlowHandler(ConfigFlow):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self.__hostname: str = TTN_API_HOSTNAME
        self.__app_id: str | None = None
        self.__access_key: str | None = None
        self.__reauth_entry: ConfigEntry | None = None

    @property
    def schema(self):
        """Return current schema."""

        return vol.Schema(
            {
                vol.Required(CONF_HOSTNAME, default=self.__hostname): str,
                vol.Required(CONF_APP_ID, default=self.__app_id): str,
                vol.Required(CONF_ACCESS_KEY, default=self.__access_key): str,
            }
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """User initiated config flow."""
        errors = {}
        if user_input is not None:
            self.__hostname = user_input[CONF_HOSTNAME]
            self.__app_id = user_input[CONF_APP_ID]
            self.__access_key = user_input[CONF_ACCESS_KEY]

            connection_error = await self.__connection_error

            if connection_error:
                errors["base"] = connection_error
            else:
                return await self.__create_or_update_entry(user_input)

        return self.async_show_form(
            step_id="user", data_schema=self.schema, errors=errors
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow initialized by a reauth event."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None
        self.__reauth_entry = entry
        self.__hostname = entry.data[CONF_HOSTNAME]
        self.__app_id = entry.data[CONF_APP_ID]
        self.__access_key = entry.data[CONF_ACCESS_KEY]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
                description_placeholders={"app_id": self.__app_id},
            )
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return TTNOptionsFlowHandler(config_entry)

    async def __create_or_update_entry(self, data):
        """Create or update TTN entry."""

        if self.__reauth_entry:
            return self.async_update_reload_and_abort(
                self.__reauth_entry,
                data=self.__reauth_entry.data | data,
                reason="reauth_successful",
            )
        if not self.unique_id:
            await self.async_set_unique_id(self.__app_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self.__app_id,
            data=data,
        )

    @property
    async def __connection_error(self) -> str | None:
        """Test if we can connect with the given settings."""

        try:
            client = TTNClient(
                self.__hostname,
                self.__app_id,
                self.__access_key,
                0,
            )
            await client.fetch_data()
            return None
        except TTNAuthError:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            _LOGGER.error("TTNAuthError")
            return "invalid_auth"

        return "connection_error"


class TTNOptionsFlowHandler(OptionsFlow):
    """Handle integration options."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.__entry = entry
        self.options = copy.deepcopy(dict(entry.options))
        self.selected_device = None
        self.selected_field = None

    def _update_entry(self, title="", data=None):
        """Update entry."""
        self.hass.config_entries.async_update_entry(
            self.__entry, data=self.__entry.data, options=self.options
        )
        return self.async_create_entry(title=title, data=self.options)

    async def async_step_init(self, user_input=None):
        """Menu selection form."""
        if user_input is not None:
            # Go to next flow step
            selected_next_step = user_input[OPTIONS_SELECTED_MENU]
            if selected_next_step == OPTIONS_MENU_EDIT_INTEGRATION:
                return await self.async_step_integration_settings()
            if selected_next_step == OPTIONS_MENU_EDIT_DEVICES:
                return await self.async_step_device_select()
            if selected_next_step == OPTIONS_MENU_EDIT_FIELDS:
                return await self.async_step_field_select()

        # Return form
        fields = OrderedDict()
        menu_options = vol.In(
            [
                OPTIONS_MENU_EDIT_INTEGRATION,
                OPTIONS_MENU_EDIT_DEVICES,
                OPTIONS_MENU_EDIT_FIELDS,
            ]
        )
        fields[
            vol.Required(OPTIONS_SELECTED_MENU, default=OPTIONS_MENU_EDIT_INTEGRATION)
        ] = menu_options
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields))

    async def async_step_integration_settings(self, user_input=None):
        """Global settings form."""

        # Get global settings
        integration_settings = self.options.setdefault(
            OPTIONS_MENU_EDIT_INTEGRATION, {}
        )

        if user_input is not None:
            # Update options
            integration_settings[
                OPTIONS_MENU_INTEGRATION_FIRST_FETCH_TIME_H
            ] = user_input[OPTIONS_MENU_INTEGRATION_FIRST_FETCH_TIME_H]
            integration_settings[OPTIONS_MENU_INTEGRATION_REFRESH_TIME_S] = user_input[
                OPTIONS_MENU_INTEGRATION_REFRESH_TIME_S
            ]

            # Return update
            return self._update_entry()

        # Get config for device
        first_fetch_time_h = integration_settings.setdefault(
            OPTIONS_MENU_INTEGRATION_FIRST_FETCH_TIME_H, DEFAULT_FIRST_FETCH_LAST_H
        )
        refresh_time_s = integration_settings.setdefault(
            OPTIONS_MENU_INTEGRATION_REFRESH_TIME_S, DEFAULT_API_REFRESH_PERIOD_S
        )

        # Return form
        fields = OrderedDict()
        fields[
            vol.Required(
                OPTIONS_MENU_INTEGRATION_FIRST_FETCH_TIME_H, default=first_fetch_time_h
            )
        ] = int
        fields[
            vol.Required(
                OPTIONS_MENU_INTEGRATION_REFRESH_TIME_S, default=refresh_time_s
            )
        ] = int
        return self.async_show_form(
            step_id="integration_settings",
            data_schema=vol.Schema(fields),
        )

    async def async_step_device_select(self, user_input=None):
        """Device selection form."""

        if user_input is not None:
            # Go to next flow step
            self.selected_device = user_input[OPTIONS_SELECTED_DEVICE]
            return await self.async_step_device_edit()

        # Get detected devices
        device_names = TTN_EntrySettings(self.__entry).get_device_ids()

        # Abort if no devices available yet
        if len(device_names) == 0:
            return self.async_abort(reason="no_devices")

        # Return form
        fields = OrderedDict()
        fields[vol.Required(OPTIONS_SELECTED_DEVICE, default=device_names[0])] = vol.In(
            device_names
        )
        return self.async_show_form(
            step_id="device_select", data_schema=vol.Schema(fields)
        )

    async def async_step_device_edit(self, user_input=None):
        """Device edit form."""
        # Get device options
        device_options = self.options.setdefault(
            OPTIONS_MENU_EDIT_DEVICES, {}
        ).setdefault(self.selected_device, {})

        if user_input is not None:
            # Update options
            device_options[OPTIONS_DEVICE_NAME] = user_input[OPTIONS_DEVICE_NAME]

            # Return update
            return self._update_entry()

        # Get config for device
        name = device_options.setdefault(OPTIONS_DEVICE_NAME, self.selected_device)

        # Return form
        fields = OrderedDict()
        fields[vol.Required(OPTIONS_DEVICE_NAME, default=name)] = str
        return self.async_show_form(
            step_id="device_edit",
            description_placeholders={OPTIONS_SELECTED_DEVICE: self.selected_device},
            data_schema=vol.Schema(fields),
        )

    async def async_step_field_select(self, user_input=None):
        """Field selection form."""

        if user_input is not None:
            # Go to next step
            self.selected_field = user_input[OPTIONS_SELECTED_FIELD]
            return await self.async_step_field_edit()

        # Get detected devices
        field_ids = TTN_EntrySettings(self.__entry).get_field_ids()

        # Abort if no devices found yet
        if len(field_ids) == 0:
            return self.async_abort(reason="no_fields")

        # Return form
        fields = OrderedDict()
        fields[vol.Required(OPTIONS_SELECTED_FIELD, default=field_ids[0])] = vol.In(
            field_ids
        )
        return self.async_show_form(
            step_id="field_select", data_schema=vol.Schema(fields)
        )

    async def async_step_field_edit(self, user_input=None):
        """Field edit form."""

        # Get field options
        field_options = self.options.setdefault(
            OPTIONS_MENU_EDIT_FIELDS, {}
        ).setdefault(self.selected_field, {})

        if user_input is not None:
            # Set empty
            field_options = self.options[OPTIONS_MENU_EDIT_FIELDS][
                self.selected_field
            ] = {}

            # Update options
            field_options[OPTIONS_FIELD_NAME] = user_input.get(OPTIONS_FIELD_NAME)
            field_options[OPTIONS_FIELD_ENTITY_TYPE] = user_input.get(
                OPTIONS_FIELD_ENTITY_TYPE
            )
            field_options[OPTIONS_FIELD_DEVICE_SCOPE] = user_input.get(
                OPTIONS_FIELD_DEVICE_SCOPE
            )
            field_options[OPTIONS_FIELD_UNIT_MEASUREMENT] = user_input.get(
                OPTIONS_FIELD_UNIT_MEASUREMENT, None
            )
            field_options[OPTIONS_FIELD_DEVICE_CLASS] = user_input.get(
                OPTIONS_FIELD_DEVICE_CLASS, None
            )
            field_options[OPTIONS_FIELD_ICON] = user_input.get(OPTIONS_FIELD_ICON, None)
            field_options[OPTIONS_FIELD_PICTURE] = user_input.get(
                OPTIONS_FIELD_PICTURE, None
            )
            field_options[OPTIONS_FIELD_SUPPORTED_FEATURES] = user_input.get(
                OPTIONS_FIELD_SUPPORTED_FEATURES, None
            )
            field_options[OPTIONS_FIELD_CONTEXT_RECENT_TIME_S] = user_input.get(
                OPTIONS_FIELD_CONTEXT_RECENT_TIME_S
            )

            # For auto type remove option
            if (
                field_options[OPTIONS_FIELD_ENTITY_TYPE]
                == OPTIONS_FIELD_ENTITY_TYPE_AUTO
            ):
                del field_options[OPTIONS_FIELD_ENTITY_TYPE]

            # For global scope remove option
            if (
                field_options[OPTIONS_FIELD_DEVICE_SCOPE]
                == OPTIONS_FIELD_DEVICE_SCOPE_GLOBAL
            ):
                del field_options[OPTIONS_FIELD_DEVICE_SCOPE]

            # Return update
            return self._update_entry()

        # Get options
        name = field_options.setdefault(OPTIONS_FIELD_NAME, self.selected_field)
        entity_type = field_options.setdefault(
            OPTIONS_FIELD_ENTITY_TYPE, OPTIONS_FIELD_ENTITY_TYPE_AUTO
        )
        device_scope = field_options.setdefault(
            OPTIONS_FIELD_DEVICE_SCOPE, OPTIONS_FIELD_DEVICE_SCOPE_GLOBAL
        )
        unit_of_measurement = field_options.setdefault(
            OPTIONS_FIELD_UNIT_MEASUREMENT, None
        )
        device_class = field_options.setdefault(OPTIONS_FIELD_DEVICE_CLASS, None)
        icon = field_options.setdefault(OPTIONS_FIELD_ICON, None)
        picture = field_options.setdefault(OPTIONS_FIELD_PICTURE, None)
        supported_features = field_options.setdefault(
            OPTIONS_FIELD_SUPPORTED_FEATURES, None
        )
        context_recent_time_s = field_options.setdefault(
            OPTIONS_FIELD_CONTEXT_RECENT_TIME_S, 5
        )

        entity_types = [
            OPTIONS_FIELD_ENTITY_TYPE_AUTO,
            OPTIONS_FIELD_ENTITY_TYPE_SENSOR,
            OPTIONS_FIELD_ENTITY_TYPE_BINARY_SENSOR,
            OPTIONS_FIELD_ENTITY_TYPE_DEVICE_TRACKER,
        ]
        device_options = vol.In(
            [OPTIONS_FIELD_DEVICE_SCOPE_GLOBAL]
            + TTN_EntrySettings(self.__entry).get_device_ids()
        )

        # Return form
        fields = OrderedDict()
        fields[vol.Required(OPTIONS_FIELD_NAME, default=name)] = str
        fields[vol.Required(OPTIONS_FIELD_ENTITY_TYPE, default=entity_type)] = vol.In(
            entity_types
        )
        fields[
            vol.Required(OPTIONS_FIELD_DEVICE_SCOPE, default=device_scope)
        ] = device_options
        fields[
            vol.Optional(
                OPTIONS_FIELD_UNIT_MEASUREMENT,
                description={"suggested_value": unit_of_measurement},
            )
        ] = str
        fields[
            vol.Optional(
                OPTIONS_FIELD_DEVICE_CLASS,
                description={"suggested_value": device_class},
            )
        ] = str
        fields[
            vol.Optional(OPTIONS_FIELD_ICON, description={"suggested_value": icon})
        ] = str
        fields[
            vol.Optional(
                OPTIONS_FIELD_PICTURE, description={"suggested_value": picture}
            )
        ] = str
        fields[
            vol.Optional(
                OPTIONS_FIELD_SUPPORTED_FEATURES,
                description={"suggested_value": supported_features},
            )
        ] = str
        fields[
            vol.Required(
                OPTIONS_FIELD_CONTEXT_RECENT_TIME_S, default=context_recent_time_s
            )
        ] = int
        return self.async_show_form(
            step_id="field_edit",
            description_placeholders={OPTIONS_SELECTED_FIELD: self.selected_field},
            data_schema=vol.Schema(fields),
        )
