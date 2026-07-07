"""Device add flow steps for the Easywave config flow."""

from typing import Any

from easywave_home_control.codec import (
    ButtonPushEvent,
    SensorLearnPayload,
    SensorTelegramEvent,
)
import voluptuous as vol

from homeassistant.config_entries import SubentryFlowResult

from .config_flow_learning import EasywaveDeviceFlowMixin
from .const import (
    CONF_BUTTON_COUNT,
    CONF_ENTRY_TYPE,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_SENSOR_CAPABILITIES,
    CONF_SENSOR_SERIAL,
    CONF_SWITCH_MODE,
    CONF_TRANSMITTER_SERIAL,
    ENTRY_TYPE_NEO_SENSOR,
    ENTRY_TYPE_TRANSMITTER,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
)

_BUTTON_COUNT_MAP: dict[str, int] = {
    "buttons_1": 1,
    "buttons_2": 2,
    "buttons_3": 3,
    "buttons_4": 4,
}


def _normalize_learned_transmitter(telegram: Any) -> dict[str, Any] | None:
    """Return learned transmitter data from a codec event."""
    if not isinstance(telegram, ButtonPushEvent):
        return None
    return {
        "serial": telegram.transmitter_serial,
        "button": telegram.button,
    }


def _normalize_learned_sensor(telegram: Any) -> dict[str, Any] | None:
    """Return learned neo sensor data from a codec event."""
    if not isinstance(telegram, SensorTelegramEvent):
        return None
    if not isinstance(telegram.payload, SensorLearnPayload):
        return None
    return {
        "serial": telegram.sensor_serial,
        "capabilities": telegram.payload.capabilities,
        "has_battery": telegram.payload.has_battery,
        "measures_temperature": telegram.payload.measures_temperature,
        "measures_humidity": telegram.payload.measures_humidity,
    }


class EasywaveDeviceAddFlowMixin(EasywaveDeviceFlowMixin):
    """Device learning steps used by the main config flow."""

    _grouping_mode: str
    _switch_mode: str
    _button_count: int

    def _init_transmitter_flow_state(self) -> None:
        """Initialize transmitter-specific flow state."""
        self._grouping_mode = TRANSMITTER_GROUPING_GROUP
        self._switch_mode = TRANSMITTER_SWITCH_IMPULSE
        self._button_count = 4

    async def async_step_transmitter(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start transmitter setup from the add-device menu."""
        self._init_transmitter_flow_state()
        self._learn_progress_action = "waiting_for_transmitter"
        self._learn_confirm_step = "transmitter_confirm"
        self._learn_step = "learn_transmitter"
        self._learn_timeout_step = "learn_timeout_transmitter"
        self._learn_back_step = "transmitter_learn_intro"
        self._accept_telegram = _normalize_learned_transmitter

        coordinator = self._get_coordinator()
        if coordinator is None or not coordinator.transceiver.is_connected:
            return self.async_abort(reason="device_not_connected")
        return await self.async_step_transmitter_learn_intro()

    async def async_step_transmitter_learn_intro(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Describe transmitter learning before button count and listen steps."""
        menu_options = ["button_count_select", "device_select"]
        return self.async_show_menu(
            step_id="transmitter_learn_intro",
            menu_options=menu_options,
        )

    async def async_step_button_count_select(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select number of transmitter buttons."""
        return self.async_show_menu(
            step_id="button_count_select",
            menu_options=[*list(_BUTTON_COUNT_MAP), "transmitter_learn_intro"],
        )

    async def _async_set_button_count(self, count_key: str) -> SubentryFlowResult:
        self._button_count = _BUTTON_COUNT_MAP[count_key]
        return await self.async_step_learn()

    async def async_step_buttons_1(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """1 button."""
        return await self._async_set_button_count("buttons_1")

    async def async_step_buttons_2(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """2 buttons."""
        return await self._async_set_button_count("buttons_2")

    async def async_step_buttons_3(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """3 buttons."""
        return await self._async_set_button_count("buttons_3")

    async def async_step_buttons_4(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """4 buttons."""
        return await self._async_set_button_count("buttons_4")

    async def async_step_transmitter_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Confirm the learned transmitter and save."""
        if self._learned_device is None:
            return self.async_abort(reason="no_device_learned")

        serial_hex = self._learned_device["serial"].hex()
        unique_id = f"transmitter_{serial_hex}"

        if self._is_duplicate(
            unique_id,
            entry_type=ENTRY_TYPE_TRANSMITTER,
            serial_hex=serial_hex,
        ):
            return self.async_abort(reason="already_configured")

        if user_input is not None and "title" in user_input:
            data: dict[str, Any] = {
                CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
                CONF_TRANSMITTER_SERIAL: serial_hex,
                CONF_OPERATING_TYPE: "1",
                CONF_BUTTON_COUNT: self._button_count,
                CONF_GROUPING_MODE: self._grouping_mode,
                CONF_SWITCH_MODE: self._switch_mode,
            }
            return self._save_device(
                title=user_input["title"],
                unique_id=unique_id,
                data=data,
            )

        return self.async_show_form(
            step_id="transmitter_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "title",
                        default=self._next_default_name(ENTRY_TYPE_TRANSMITTER),
                    ): str,
                }
            ),
        )

    async def async_step_neo_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start neo sensor setup from the add-device menu."""
        self._learn_progress_action = "waiting_for_sensor"
        self._learn_confirm_step = "sensor_confirm"
        self._learn_step = "learn_sensor"
        self._learn_timeout_step = "learn_timeout_sensor"
        self._learn_back_step = "sensor_learn_intro"
        self._accept_telegram = _normalize_learned_sensor

        coordinator = self._get_coordinator()
        if coordinator is None or not coordinator.transceiver.is_connected:
            return self.async_abort(reason="device_not_connected")
        return await self.async_step_sensor_learn_intro()

    async def async_step_sensor_learn_intro(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Describe neo sensor learning before starting the listen step."""
        menu_options = ["learn", "device_select"]
        return self.async_show_menu(
            step_id="sensor_learn_intro",
            menu_options=menu_options,
        )

    async def async_step_sensor_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Confirm the learned neo sensor and save."""
        if self._learned_device is None:
            return self.async_abort(reason="no_device_learned")

        serial_hex = self._learned_device["serial"].hex()
        unique_id = f"neo_sensor_{serial_hex}"

        if self._is_duplicate(
            unique_id,
            entry_type=ENTRY_TYPE_NEO_SENSOR,
            serial_hex=serial_hex,
        ):
            return self.async_abort(reason="already_configured")

        if user_input is not None and "title" in user_input:
            data: dict[str, Any] = {
                CONF_ENTRY_TYPE: ENTRY_TYPE_NEO_SENSOR,
                CONF_SENSOR_SERIAL: serial_hex,
                CONF_SENSOR_CAPABILITIES: self._learned_device["capabilities"],
            }
            return self._save_device(
                title=user_input["title"],
                unique_id=unique_id,
                data=data,
            )

        return self.async_show_form(
            step_id="sensor_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "title",
                        default=self._next_default_name(ENTRY_TYPE_NEO_SENSOR),
                    ): str,
                }
            ),
            description_placeholders={
                "sensor_list": await self._async_format_neo_sensor_list(
                    self._learned_device
                ),
            },
        )
