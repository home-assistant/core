"""Config flow for AlarmDecoder."""

from collections.abc import Mapping
import logging
from typing import Any, cast, override

from adext import AdExt
from alarmdecoder.devices import Device, SerialDevice, SocketDevice
from alarmdecoder.util import NoDeviceError
import probatio

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PROTOCOL
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_ALT_NIGHT_MODE,
    CONF_AUTO_BYPASS,
    CONF_CODE_ARM_REQUIRED,
    CONF_DEVICE_BAUD,
    CONF_DEVICE_PATH,
    CONF_RELAY_ADDR,
    CONF_RELAY_CHAN,
    CONF_ZONE_LOOP,
    CONF_ZONE_NAME,
    CONF_ZONE_NUMBER,
    CONF_ZONE_RFID,
    CONF_ZONE_TYPE,
    DEFAULT_ARM_OPTIONS,
    DEFAULT_DEVICE_BAUD,
    DEFAULT_DEVICE_HOST,
    DEFAULT_DEVICE_PATH,
    DEFAULT_DEVICE_PORT,
    DEFAULT_ZONE_OPTIONS,
    DEFAULT_ZONE_TYPE,
    DOMAIN,
    OPTIONS_ARM,
    OPTIONS_ZONES,
    PROTOCOL_SERIAL,
    PROTOCOL_SOCKET,
)

EDIT_KEY = "edit_selection"
EDIT_ZONES = "Zones"
EDIT_SETTINGS = "Arming Settings"
DEFAULT_CONNECTION = {
    CONF_HOST: DEFAULT_DEVICE_HOST,
    CONF_PORT: DEFAULT_DEVICE_PORT,
    CONF_DEVICE_PATH: DEFAULT_DEVICE_PATH,
    CONF_DEVICE_BAUD: DEFAULT_DEVICE_BAUD,
}

_LOGGER = logging.getLogger(__name__)


class AlarmDecoderFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a AlarmDecoder config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize AlarmDecoder ConfigFlow."""
        self.protocol = None

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AlarmDecoderOptionsFlowHandler:
        """Get the options flow for AlarmDecoder."""
        return AlarmDecoderOptionsFlowHandler(config_entry)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.protocol = user_input[CONF_PROTOCOL]
            return await self.async_step_protocol()

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_PROTOCOL): probatio.In(
                        [PROTOCOL_SOCKET, PROTOCOL_SERIAL]
                    ),
                }
            ),
        )

    async def async_step_protocol(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle AlarmDecoder protocol setup."""
        errors = {}
        if user_input is not None:
            if _device_already_added(
                self._async_current_entries(), user_input, self.protocol
            ):
                return self.async_abort(reason="already_configured")
            errors = await _async_test_connection(self.hass, self.protocol, user_input)
            if not errors:
                return self.async_create_entry(
                    title=_connection_title(self.protocol, user_input),
                    data={CONF_PROTOCOL: self.protocol, **user_input},
                )

        return self.async_show_form(
            step_id="protocol",
            data_schema=_connection_schema(self.protocol, DEFAULT_CONNECTION),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the connection settings of an existing entry."""
        entry = self._get_reconfigure_entry()
        protocol = entry.data[CONF_PROTOCOL]
        errors = {}
        if user_input is not None:
            other_entries = [
                other
                for other in self._async_current_entries()
                if other.entry_id != entry.entry_id
            ]
            if _device_already_added(other_entries, user_input, protocol):
                return self.async_abort(reason="already_configured")
            errors = await _async_test_connection(self.hass, protocol, user_input)
            if not errors:
                # Keep a title the user chose; replace the generated one.
                title = entry.title
                if title == _connection_title(protocol, entry.data):
                    title = _connection_title(protocol, user_input)
                # The entry's update listener reloads it.
                return self.async_update_and_abort(
                    entry, title=title, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(protocol, entry.data),
            errors=errors,
        )


class AlarmDecoderOptionsFlowHandler(OptionsFlow):
    """Handle AlarmDecoder options."""

    selected_zone: str

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize AlarmDecoder options flow."""
        self.arm_options = config_entry.options.get(OPTIONS_ARM, DEFAULT_ARM_OPTIONS)
        self.zone_options = config_entry.options.get(
            OPTIONS_ZONES, DEFAULT_ZONE_OPTIONS
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input[EDIT_KEY] == EDIT_SETTINGS:
                return await self.async_step_arm_settings()
            if user_input[EDIT_KEY] == EDIT_ZONES:
                return await self.async_step_zone_select()

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(EDIT_KEY, default=EDIT_SETTINGS): probatio.In(
                        [EDIT_SETTINGS, EDIT_ZONES]
                    )
                },
            ),
        )

    async def async_step_arm_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Arming options form."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={OPTIONS_ARM: user_input, OPTIONS_ZONES: self.zone_options},
            )

        return self.async_show_form(
            step_id="arm_settings",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_ALT_NIGHT_MODE,
                        default=self.arm_options[CONF_ALT_NIGHT_MODE],
                    ): bool,
                    probatio.Optional(
                        CONF_AUTO_BYPASS, default=self.arm_options[CONF_AUTO_BYPASS]
                    ): bool,
                    probatio.Optional(
                        CONF_CODE_ARM_REQUIRED,
                        default=self.arm_options[CONF_CODE_ARM_REQUIRED],
                    ): bool,
                },
            ),
        )

    async def async_step_zone_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Zone selection form."""
        errors = _validate_zone_input(user_input)

        if user_input is not None and not errors:
            self.selected_zone = str(
                int(user_input[CONF_ZONE_NUMBER])
            )  # remove leading zeros
            return await self.async_step_zone_details()

        return self.async_show_form(
            step_id="zone_select",
            data_schema=probatio.Schema({probatio.Required(CONF_ZONE_NUMBER): str}),
            errors=errors,
        )

    async def async_step_zone_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Zone details form."""
        errors = _validate_zone_input(user_input)

        if user_input is not None and not errors:
            zone_options = self.zone_options.copy()
            zone_id = self.selected_zone
            zone_options[zone_id] = _fix_input_types(user_input)

            # Delete zone entry if zone_name is omitted
            if CONF_ZONE_NAME not in zone_options[zone_id]:
                zone_options.pop(zone_id)

            return self.async_create_entry(
                title="",
                data={OPTIONS_ARM: self.arm_options, OPTIONS_ZONES: zone_options},
            )

        existing_zone_settings = self.zone_options.get(self.selected_zone, {})

        return self.async_show_form(
            step_id="zone_details",
            description_placeholders={CONF_ZONE_NUMBER: self.selected_zone},
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_ZONE_NAME,
                        description={
                            "suggested_value": existing_zone_settings.get(
                                CONF_ZONE_NAME
                            )
                        },
                    ): str,
                    probatio.Optional(
                        CONF_ZONE_TYPE,
                        default=existing_zone_settings.get(
                            CONF_ZONE_TYPE, DEFAULT_ZONE_TYPE
                        ),
                    ): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
                    probatio.Optional(
                        CONF_ZONE_RFID,
                        description={
                            "suggested_value": existing_zone_settings.get(
                                CONF_ZONE_RFID
                            )
                        },
                    ): str,
                    probatio.Optional(
                        CONF_ZONE_LOOP,
                        description={
                            "suggested_value": existing_zone_settings.get(
                                CONF_ZONE_LOOP
                            )
                        },
                    ): str,
                    probatio.Optional(
                        CONF_RELAY_ADDR,
                        description={
                            "suggested_value": existing_zone_settings.get(
                                CONF_RELAY_ADDR
                            )
                        },
                    ): str,
                    probatio.Optional(
                        CONF_RELAY_CHAN,
                        description={
                            "suggested_value": existing_zone_settings.get(
                                CONF_RELAY_CHAN
                            )
                        },
                    ): str,
                }
            ),
            errors=errors,
        )


def _validate_zone_input(zone_input: dict[str, Any] | None) -> dict[str, str]:
    if not zone_input:
        return {}
    errors = {}

    # CONF_RELAY_ADDR & CONF_RELAY_CHAN are inclusive
    if (CONF_RELAY_ADDR in zone_input and CONF_RELAY_CHAN not in zone_input) or (
        CONF_RELAY_ADDR not in zone_input and CONF_RELAY_CHAN in zone_input
    ):
        errors["base"] = "relay_inclusive"

    # The following keys must be int
    for key in (CONF_ZONE_NUMBER, CONF_ZONE_LOOP, CONF_RELAY_ADDR, CONF_RELAY_CHAN):
        if key in zone_input:
            try:
                int(zone_input[key])
            except ValueError:
                errors[key] = "int"

    # CONF_ZONE_LOOP depends on CONF_ZONE_RFID
    if CONF_ZONE_LOOP in zone_input and CONF_ZONE_RFID not in zone_input:
        errors[CONF_ZONE_LOOP] = "loop_rfid"

    # CONF_ZONE_LOOP must be 1-4
    if (
        CONF_ZONE_LOOP in zone_input
        and zone_input[CONF_ZONE_LOOP].isdigit()
        and int(zone_input[CONF_ZONE_LOOP]) not in list(range(1, 5))
    ):
        errors[CONF_ZONE_LOOP] = "loop_range"

    return errors


def _fix_input_types(zone_input: dict[str, Any]) -> dict[str, Any]:
    """Convert necessary keys to int.

    Since ConfigFlow inputs of type int cannot default to an empty
    string, we collect the values below as strings and then convert
    them to ints.
    """

    for key in (CONF_ZONE_LOOP, CONF_RELAY_ADDR, CONF_RELAY_CHAN):
        if key in zone_input:
            zone_input[key] = int(zone_input[key])

    return zone_input


def _device_already_added(
    current_entries: list[ConfigEntry], user_input: dict[str, Any], protocol: str | None
) -> bool:
    """Determine if entry has already been added to HA."""
    user_host = user_input.get(CONF_HOST)
    user_port = user_input.get(CONF_PORT)
    user_path = user_input.get(CONF_DEVICE_PATH)
    user_baud = user_input.get(CONF_DEVICE_BAUD)

    for entry in current_entries:
        entry_host = entry.data.get(CONF_HOST)
        entry_port = entry.data.get(CONF_PORT)
        entry_path = entry.data.get(CONF_DEVICE_PATH)
        entry_baud = entry.data.get(CONF_DEVICE_BAUD)

        if (
            protocol == PROTOCOL_SOCKET
            and user_host == entry_host
            and user_port == entry_port
        ):
            return True

        if (
            protocol == PROTOCOL_SERIAL
            and user_baud == entry_baud
            and user_path == entry_path
        ):
            return True

    return False


def _connection_schema(
    protocol: str | None, defaults: Mapping[str, Any]
) -> probatio.Schema:
    """Return the connection settings schema for a protocol."""
    if protocol == PROTOCOL_SOCKET:
        return probatio.Schema(
            {
                probatio.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
                probatio.Required(CONF_PORT, default=defaults[CONF_PORT]): int,
            }
        )
    return probatio.Schema(
        {
            probatio.Required(
                CONF_DEVICE_PATH, default=defaults[CONF_DEVICE_PATH]
            ): str,
            probatio.Required(
                CONF_DEVICE_BAUD, default=defaults[CONF_DEVICE_BAUD]
            ): int,
        }
    )


def _connection_title(protocol: str | None, connection: Mapping[str, Any]) -> str:
    """Return the entry title generated for connection settings."""
    if protocol == PROTOCOL_SOCKET:
        return f"{connection[CONF_HOST]}:{connection[CONF_PORT]}"
    return cast(str, connection[CONF_DEVICE_PATH])


async def _async_test_connection(
    hass: HomeAssistant, protocol: str | None, connection: dict[str, Any]
) -> dict[str, str]:
    """Open and close a connection to the AlarmDecoder; return form errors."""
    baud = None
    device: Device
    if protocol == PROTOCOL_SOCKET:
        device = SocketDevice(interface=(connection[CONF_HOST], connection[CONF_PORT]))
    else:
        device = SerialDevice(interface=connection[CONF_DEVICE_PATH])
        baud = connection[CONF_DEVICE_BAUD]
    controller = AdExt(device)

    def test_connection() -> None:
        controller.open(baud)
        controller.close()

    try:
        await hass.async_add_executor_job(test_connection)
    except NoDeviceError:
        return {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unexpected exception connecting to the AlarmDecoder")
        return {"base": "unknown"}
    return {}
