"""Handle the configuration flow for the Gryf Smart integration."""

import logging
from types import MappingProxyType
from typing import Any
import uuid

from pygryfsmart.rs232 import RS232Handler
from serial import SerialException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_COMMUNICATION,
    CONF_DEVICES,
    CONF_EXTRA,
    CONF_ID,
    CONF_MODULE_COUNT,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
    CONFIG_FLOW_MENU_OPTIONS,
    DEFAULT_PORT,
    DEVICE_TYPES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def ping_connection(port) -> bool:
    """Test connection."""
    writer = RS232Handler(port, 115200)
    try:
        await writer.open_connection()
        await writer.close_connection()
        return True
    except SerialException as e:
        _LOGGER.error("%s", e)
        return False
    else:
        return True


class GryfSmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gryf Smart ConfigFlow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize Gryf Smart ConfigFlow."""
        super().__init__()
        self._config_data: dict[str, Any] = {}
        self._config_data[CONF_DEVICES] = []
        self._current_device: dict[str, Any]
        self._edit_index: int | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """First config flow step, selecting communication parameters."""

        errors = {}

        if user_input:
            if not await ping_connection(user_input.get(CONF_PORT)):
                errors[CONF_PORT] = "Unable to connect"
            elif not user_input.get(CONF_PORT, "").startswith("/dev/"):
                errors[CONF_PORT] = "invalid_port"
            else:
                self._config_data = {
                    CONF_COMMUNICATION: {},
                    CONF_DEVICES: [],
                }

                self._config_data[CONF_COMMUNICATION][CONF_PORT] = user_input[CONF_PORT]
                self._config_data[CONF_COMMUNICATION][CONF_MODULE_COUNT] = user_input[
                    CONF_MODULE_COUNT
                ]

                return await self.async_step_device_menu()

        await self.async_set_unique_id(str(uuid.uuid4()))
        self._abort_if_unique_id_configured()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): str,
                    vol.Required(CONF_MODULE_COUNT, default=1): int,
                }
            ),
            errors=errors,
        )

    async def async_step_device_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show menu step."""

        return self.async_show_menu(
            step_id="device_menu",
            menu_options=CONFIG_FLOW_MENU_OPTIONS,
        )

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add new device."""
        if user_input:
            new_device = {
                CONF_TYPE: user_input[CONF_TYPE],
                CONF_NAME: user_input[CONF_NAME],
                CONF_ID: user_input[CONF_ID],
                CONF_EXTRA: user_input.get(CONF_EXTRA),
            }
            self._config_data[CONF_DEVICES].append(new_device)
            return await self.async_step_device_menu()

        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TYPE): vol.In(DEVICE_TYPES),
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_ID): int,
                    vol.Optional(CONF_EXTRA): int,
                }
            ),
        )

    async def async_step_edit_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select device to edit."""
        if not self._config_data[CONF_DEVICES]:
            return await self.async_step_device_menu()

        if user_input:
            self._edit_index = int(user_input["device_index"])
            self._current_device = self._config_data[CONF_DEVICES][
                self._edit_index
            ].copy()
            return await self.async_step_edit_device_details()

        devices = [
            selector.SelectOptionDict(
                value=str(idx), label=f"{dev[CONF_NAME]} (ID: {dev[CONF_ID]})"
            )
            for idx, dev in enumerate(self._config_data[CONF_DEVICES])
        ]

        return self.async_show_form(
            step_id="edit_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=devices)
                    )
                }
            ),
        )

    async def async_step_edit_device_details(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit device parameters."""
        if user_input:
            self._config_data[CONF_DEVICES][self._edit_index] = user_input
            self._edit_index = None
            return await self.async_step_device_menu()

        return self.async_show_form(
            step_id="edit_device_details",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TYPE, default=self._current_device[CONF_TYPE]
                    ): vol.In(DEVICE_TYPES),
                    vol.Required(
                        CONF_NAME, default=self._current_device[CONF_NAME]
                    ): str,
                    vol.Required(CONF_ID, default=self._current_device[CONF_ID]): int,
                    vol.Optional(
                        CONF_EXTRA, default=self._current_device.get(CONF_EXTRA)
                    ): int,
                }
            ),
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Finish the config flow."""
        return self.async_create_entry(
            title=f"GryfSmart: {self._config_data[CONF_COMMUNICATION][CONF_PORT]}",
            data=self._config_data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""

        return GryfSmartOptionsFlow()


class GryfSmartOptionsFlow(config_entries.OptionsFlow):
    """Handle the options flow for the Gryf Smart Integration."""

    _edit_index: int
    data: MappingProxyType[str, Any]
    _current_device: dict

    def __init__(self) -> None:
        """Initialize OptionsFlow."""
        self._edit_index = 0
        self._current_device = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Initialize the Gryf Smart options flow."""
        self.data = self.config_entry.data
        _LOGGER.debug("%s", self.data)
        return await self.async_step_main_menu()

    async def async_step_main_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show main options menu."""
        return self.async_show_menu(
            step_id="main_menu", menu_options=CONFIG_FLOW_MENU_OPTIONS
        )

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add new device."""
        if user_input:
            new_device = {
                CONF_TYPE: user_input[CONF_TYPE],
                CONF_NAME: user_input[CONF_NAME],
                CONF_ID: user_input[CONF_ID],
                CONF_EXTRA: user_input.get(CONF_EXTRA),
            }
            self.data["devices"].append(new_device)
            return await self.async_step_main_menu()

        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TYPE): vol.In(DEVICE_TYPES),
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_ID): int,
                    vol.Optional(CONF_EXTRA): int,
                }
            ),
        )

    async def async_step_edit_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select device to edit."""
        if not self.data[CONF_DEVICES]:
            return await self.async_step_main_menu()

        if user_input:
            self._edit_index = int(user_input["device_index"])
            self._current_device = self.data[CONF_DEVICES][self._edit_index].copy()
            return await self.async_step_edit_device_details()

        devices = [
            selector.SelectOptionDict(
                value=str(idx), label=f"{dev[CONF_NAME]} (ID: {dev[CONF_ID]})"
            )
            for idx, dev in enumerate(self.data[CONF_DEVICES])
        ]

        return self.async_show_form(
            step_id="edit_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=devices)
                    )
                }
            ),
        )

    async def async_step_edit_device_details(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit device parameters."""
        if user_input:
            self.data[CONF_DEVICES][self._edit_index] = user_input
            self._edit_index = 0
            return await self.async_step_main_menu()

        if self._current_device.get(CONF_EXTRA) is not None:
            return self.async_show_form(
                step_id="edit_device_details",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_TYPE, default=self._current_device[CONF_TYPE]
                        ): vol.In(DEVICE_TYPES),
                        vol.Required(
                            CONF_NAME, default=self._current_device[CONF_NAME]
                        ): str,
                        vol.Required(
                            CONF_ID, default=self._current_device[CONF_ID]
                        ): int,
                        vol.Optional(
                            CONF_EXTRA, default=self._current_device.get(CONF_EXTRA)
                        ): int,
                    }
                ),
            )
        return self.async_show_form(
            step_id="edit_device_details",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TYPE, default=self._current_device[CONF_TYPE]
                    ): vol.In(DEVICE_TYPES),
                    vol.Required(
                        CONF_NAME, default=self._current_device[CONF_NAME]
                    ): str,
                    vol.Required(CONF_ID, default=self._current_device[CONF_ID]): int,
                    vol.Optional(CONF_EXTRA): int,
                }
            ),
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Finish config flow."""
        return self.async_create_entry(data=self.data)

    async def async_step_communication(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show communication form."""
        errors = {}
        if user_input:
            if not await ping_connection(user_input.get(CONF_PORT)):
                errors[CONF_PORT] = "Unable to connect"
            elif not user_input.get(CONF_PORT, "").startswith("/dev/"):
                errors[CONF_PORT] = "invalid_port"
            else:
                self.data[CONF_COMMUNICATION][CONF_PORT] = user_input[CONF_PORT]
                self.data[CONF_COMMUNICATION][CONF_MODULE_COUNT] = user_input[
                    CONF_MODULE_COUNT
                ]

                return await self.async_step_main_menu()

        return self.async_show_form(
            step_id="communication",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PORT, default=self.data[CONF_COMMUNICATION][CONF_PORT]
                    ): str,
                    vol.Required(
                        CONF_MODULE_COUNT,
                        default=self.data[CONF_COMMUNICATION][CONF_MODULE_COUNT],
                    ): int,
                }
            ),
            errors=errors,
        )
