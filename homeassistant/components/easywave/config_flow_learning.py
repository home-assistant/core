"""Shared config flow helpers for Easywave device learning."""

import asyncio
from collections.abc import Mapping
import time
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry, SubentryFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_DEVICES
from homeassistant.helpers import translation

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import (
    CONF_DEVICE_DATA,
    CONF_DEVICE_TITLE,
    CONF_ENTRY_TYPE,
    CONF_SENSOR_SERIAL,
    CONF_TRANSMITTER_SERIAL,
    DOMAIN,
    ENTRY_TYPE_NEO_SENSOR,
    ENTRY_TYPE_TRANSMITTER,
    LEARNING_TIMEOUT,
)


class EasywaveDeviceFlowMixin:
    """Shared helpers and learning-timeout steps for device flows."""

    if TYPE_CHECKING:
        hass: HomeAssistant

        def _get_entry(self) -> ConfigEntry:
            """Return the config entry linked to the current flow."""

        def async_abort(
            self,
            *,
            reason: str,
            description_placeholders: Mapping[str, str] | None = None,
        ) -> SubentryFlowResult:
            """Abort the flow."""

        def async_show_form(self, *args: Any, **kwargs: Any) -> SubentryFlowResult:
            """Show a form step."""

        def async_show_menu(self, *args: Any, **kwargs: Any) -> SubentryFlowResult:
            """Show a menu step."""

        def async_show_progress(self, *args: Any, **kwargs: Any) -> SubentryFlowResult:
            """Show a progress step."""

        def async_show_progress_done(
            self, *args: Any, **kwargs: Any
        ) -> SubentryFlowResult:
            """Finish a progress step."""

    _learn_task: asyncio.Task[dict[str, Any] | None] | None
    _learned_device: dict[str, Any] | None
    _learn_progress_action: str
    _learn_confirm_step: str
    _learn_step: str
    _learn_timeout_step: str
    _learn_back_step: str
    _accept_telegram: Any

    def _init_device_flow(self) -> None:
        """Initialize shared device-learning state fields."""
        self._learn_task = None
        self._learned_device = None
        self._learn_progress_action = ""
        self._learn_confirm_step = ""
        self._learn_step = "learn"
        self._learn_timeout_step = "learn_timeout_transmitter"
        self._learn_back_step = ""
        self._accept_telegram = None

    def _get_coordinator(self) -> Any | None:
        """Return the gateway coordinator or None."""
        entry = self._get_entry()
        if entry.runtime_data is not None:
            return entry.runtime_data.coordinator
        return None

    def _configured_devices(self) -> list[dict[str, Any]]:
        """Return device records stored in the gateway config entry options."""
        return list(self._get_entry().options.get(CONF_DEVICES, []))

    def _is_duplicate(
        self,
        unique_id: str,
        *,
        entry_type: str | None = None,
        serial_hex: str | None = None,
    ) -> bool:
        """Return True if a device with this id or serial is already configured."""
        devices = self._configured_devices()
        if any(device[CONF_DEVICE_ID] == unique_id for device in devices):
            return True
        if serial_hex is None or entry_type is None:
            return False
        serial_key = {
            ENTRY_TYPE_TRANSMITTER: CONF_TRANSMITTER_SERIAL,
            ENTRY_TYPE_NEO_SENSOR: CONF_SENSOR_SERIAL,
        }.get(entry_type)
        if serial_key is None:
            return False
        return any(
            device[CONF_DEVICE_DATA].get(serial_key) == serial_hex for device in devices
        )

    def _save_device(
        self, title: str, unique_id: str, data: dict[str, Any]
    ) -> SubentryFlowResult:
        """Persist a new device in the gateway config entry options."""
        entry = self._get_entry()
        devices = self._configured_devices()
        devices.append(
            {
                CONF_DEVICE_ID: unique_id,
                CONF_DEVICE_TITLE: title,
                CONF_DEVICE_DATA: data,
            }
        )
        self.hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_DEVICES: devices},
        )
        return self.async_abort(
            reason="device_added",
            description_placeholders={"device_name": title},
        )

    async def _async_format_neo_sensor_list(
        self, learned_device: dict[str, Any]
    ) -> str:
        """Return a translated bullet list of supported neo sensor measurements."""
        language = self.hass.config.language
        entity_translations = await translation.async_get_translations(
            self.hass, language, "entity", integrations=[DOMAIN]
        )
        selector_translations = await translation.async_get_translations(
            self.hass, language, "selector", integrations=[DOMAIN]
        )
        entity_prefix = f"component.{DOMAIN}.entity.sensor."
        items: list[str] = []
        if learned_device.get("measures_temperature"):
            items.append(
                entity_translations[f"{entity_prefix}neo_sensor_temperature.name"]
            )
        if learned_device.get("measures_humidity"):
            items.append(
                entity_translations[f"{entity_prefix}neo_sensor_humidity.name"]
            )
        if not items:
            unknown = selector_translations[
                f"component.{DOMAIN}.selector.sensor_type.options.unknown"
            ]
            return f"• {unknown}"
        return "\n".join(f"• {name}" for name in items)

    def _next_default_name(self, entry_type: str) -> str:
        """Return a suggested device name based on the existing device count."""
        devices = self._configured_devices()
        if entry_type == ENTRY_TYPE_TRANSMITTER:
            count = sum(
                1
                for device in devices
                if device[CONF_DEVICE_DATA].get(CONF_ENTRY_TYPE)
                == ENTRY_TYPE_TRANSMITTER
            )
            return f"Easywave Transmitter {count + 1}"
        if entry_type == ENTRY_TYPE_NEO_SENSOR:
            count = sum(
                1
                for device in devices
                if device[CONF_DEVICE_DATA].get(CONF_ENTRY_TYPE)
                == ENTRY_TYPE_NEO_SENSOR
            )
            return f"Easywave neo Sensor {count + 1}"
        return ""

    async def _await_learning_task(
        self,
        *,
        progress_action: str,
        confirm_step: str,
        learn_step: str,
    ) -> SubentryFlowResult:
        """Run or collect a background learning task with progress UI."""
        coordinator = self._get_coordinator()
        if coordinator is None or not coordinator.transceiver.is_connected:
            return self.async_abort(reason="device_not_connected")

        if self._learn_task is None:
            self._learn_task = self.hass.async_create_task(
                self._do_learning(coordinator),
                "easywave_device_learning",
            )

        if not self._learn_task.done():
            return self.async_show_progress(
                step_id=learn_step,
                progress_action=progress_action,
                progress_task=self._learn_task,
            )

        try:
            result = self._learn_task.result()
        except OSError, TimeoutError, asyncio.CancelledError:
            result = None
        finally:
            self._learn_task = None

        if result is None:
            return self.async_show_progress_done(next_step_id=self._learn_timeout_step)

        self._learned_device = result
        return self.async_show_progress_done(next_step_id=confirm_step)

    async def _do_learning(self, coordinator: Any) -> dict[str, Any] | None:
        """Wait for a device telegram."""
        if self._accept_telegram is None:
            raise NotImplementedError
        return await self._listen_for_telegram(
            coordinator, accept_telegram=self._accept_telegram
        )

    async def async_step_learn_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle learning timeout - offer retry, back, or abort."""
        menu_options = ["learn", self._learn_back_step, "abort_learn"]
        return self.async_show_menu(
            step_id=self._learn_timeout_step,
            menu_options=menu_options,
        )

    async def async_step_learn_timeout_transmitter(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle transmitter learning timeout."""
        return await self.async_step_learn_timeout(user_input)

    async def async_step_learn_timeout_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle neo sensor learning timeout."""
        return await self.async_step_learn_timeout(user_input)

    async def async_step_learn(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Retry learning after a timeout."""
        return await self._await_learning_task(
            progress_action=self._learn_progress_action,
            confirm_step=self._learn_confirm_step,
            learn_step=self._learn_step,
        )

    async def async_step_learn_transmitter(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show transmitter learning progress."""
        return await self.async_step_learn(user_input)

    async def async_step_learn_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show neo sensor learning progress."""
        return await self.async_step_learn(user_input)

    async def async_step_abort_learn(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Abort the learning flow."""
        return self.async_abort(reason="learning_cancelled")

    async def _listen_for_telegram(
        self, coordinator: Any, *, accept_telegram: Any
    ) -> dict[str, Any] | None:
        """Listen for a matching telegram with exclusive hardware access."""
        await coordinator.suspend_telegram_listener()
        try:
            deadline = time.monotonic() + LEARNING_TIMEOUT
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                telegram = await coordinator.transceiver.receive_telegram(
                    timeout=min(remaining, 10.0)
                )
                if telegram is None:
                    continue
                if learned := accept_telegram(telegram):
                    return learned
        finally:
            coordinator.resume_telegram_listener()
        return None
