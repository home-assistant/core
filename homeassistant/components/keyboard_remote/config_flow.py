"""Config flow for Keyboard Remote."""

from __future__ import annotations

import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_DESCRIPTOR,
    CONF_DEVICE_NAME,
    CONF_DEVICE_PATH,
    CONF_EMULATE_KEY_HOLD,
    CONF_EMULATE_KEY_HOLD_DELAY,
    CONF_EMULATE_KEY_HOLD_REPEAT,
    CONF_KEY_TYPES,
    DEFAULT_EMULATE_KEY_HOLD,
    DEFAULT_EMULATE_KEY_HOLD_DELAY,
    DEFAULT_EMULATE_KEY_HOLD_REPEAT,
    DEFAULT_KEY_TYPES,
    DEVINPUT,
    DEVINPUT_BY_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _get_device_name(device_path: str) -> str | None:
    """Open an input device and return its name, or None on error."""
    from evdev import InputDevice  # noqa: PLC0415

    try:
        dev = InputDevice(os.path.realpath(device_path))
    except OSError:
        return None
    try:
        return dev.name
    finally:
        dev.close()


def _scan_input_devices_sync() -> list[selector.SelectOptionDict]:
    """Scan /dev/input/by-id/ and return selectable device options."""
    from evdev import InputDevice  # noqa: PLC0415

    options: list[selector.SelectOptionDict] = []

    if not os.path.isdir(DEVINPUT_BY_ID):
        return options

    for entry in sorted(os.scandir(DEVINPUT_BY_ID), key=lambda e: e.name):
        if not entry.is_symlink():
            continue
        real_path = os.path.realpath(entry.path)
        try:
            dev = InputDevice(real_path)
        except OSError:
            continue
        try:
            label = f"{dev.name} ({entry.name})"
        finally:
            dev.close()
        options.append(selector.SelectOptionDict(value=entry.path, label=label))

    return options


async def _scan_input_devices(
    hass: HomeAssistant,
) -> list[selector.SelectOptionDict]:
    """Scan /dev/input/by-id/ and return selectable device options."""
    return await hass.async_add_executor_job(_scan_input_devices_sync)


def _resolve_yaml_device(
    import_data: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    """Resolve YAML device config to (device_path, device_name, unique_id).

    Returns (None, None, None) if device cannot be resolved at all.
    Returns (path, name, unique_id) where unique_id is the by-id basename
    if available, or None if no by-id symlink can be found.
    """
    from evdev import InputDevice, list_devices  # noqa: PLC0415

    descriptor = import_data.get("device_descriptor")
    name = import_data.get("device_name")

    # Build realpath -> by-id mapping
    by_id_map: dict[str, str] = {}
    if os.path.isdir(DEVINPUT_BY_ID):
        with os.scandir(DEVINPUT_BY_ID) as entries:
            for entry in entries:
                if entry.is_symlink():
                    by_id_map[os.path.realpath(entry.path)] = entry.path

    if descriptor:
        real_path = os.path.realpath(descriptor)
        try:
            dev = InputDevice(real_path)
        except OSError:
            dev_name = None
        else:
            try:
                dev_name = dev.name
            finally:
                dev.close()

        if real_path in by_id_map:
            by_id_path = by_id_map[real_path]
            return (by_id_path, dev_name, os.path.basename(by_id_path))
        # No by-id symlink; return raw path, no stable unique_id
        return (descriptor, dev_name, None)

    if name:
        for dev_path in list_devices(DEVINPUT):
            try:
                dev = InputDevice(dev_path)
            except OSError:
                continue
            try:
                dev_name = dev.name
            finally:
                dev.close()
            if dev_name == name:
                real_path = os.path.realpath(dev_path)
                if real_path in by_id_map:
                    by_id_path = by_id_map[real_path]
                    return (by_id_path, name, os.path.basename(by_id_path))
                return (dev_path, name, None)

    return (None, None, None)


class KeyboardRemoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Keyboard Remote."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> KeyboardRemoteOptionsFlow:
        """Get the options flow for this handler."""
        return KeyboardRemoteOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick an input device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_path = user_input[CONF_DEVICE_PATH]
            unique_id = os.path.basename(device_path)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            dev_name = await self.hass.async_add_executor_job(
                _get_device_name, device_path
            )
            if dev_name is None:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=dev_name,
                    data={
                        CONF_DEVICE_PATH: device_path,
                        CONF_DEVICE_NAME: dev_name,
                    },
                    options={
                        CONF_KEY_TYPES: DEFAULT_KEY_TYPES,
                        CONF_EMULATE_KEY_HOLD: DEFAULT_EMULATE_KEY_HOLD,
                        CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
                        CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
                    },
                )

        available_devices = await _scan_input_devices(self.hass)

        if not available_devices:
            return self.async_abort(reason="no_devices")

        configured_ids = {entry.unique_id for entry in self._async_current_entries()}
        available_devices = [
            d
            for d in available_devices
            if os.path.basename(d["value"]) not in configured_ids
        ]

        if not available_devices:
            return self.async_abort(reason="all_devices_configured")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_PATH): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=available_devices,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            sort=False,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a single device from YAML configuration."""
        device_path, device_name, unique_id = await self.hass.async_add_executor_job(
            _resolve_yaml_device, import_data
        )

        # Determine unique ID and fallback identity
        if unique_id is None:
            raw_descriptor = import_data.get("device_descriptor")
            raw_name = import_data.get("device_name")
            if raw_descriptor:
                unique_id = raw_descriptor
                device_path = device_path or raw_descriptor
                device_name = device_name or raw_descriptor
            elif raw_name:
                unique_id = raw_name
                device_path = device_path or raw_name
                device_name = raw_name
            else:
                return self.async_abort(reason="cannot_identify_device")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Build entry data
        data: dict[str, Any] = {CONF_DEVICE_PATH: device_path}
        if device_name:
            data[CONF_DEVICE_NAME] = device_name
        # Store original YAML descriptor for runtime matching
        if raw_descriptor := import_data.get("device_descriptor"):
            data[CONF_DEVICE_DESCRIPTOR] = raw_descriptor

        # Map YAML options
        key_types = import_data.get("type", DEFAULT_KEY_TYPES)
        emulate_hold = import_data.get("emulate_key_hold", DEFAULT_EMULATE_KEY_HOLD)
        emulate_delay = import_data.get(
            "emulate_key_hold_delay", DEFAULT_EMULATE_KEY_HOLD_DELAY
        )
        emulate_repeat = import_data.get(
            "emulate_key_hold_repeat", DEFAULT_EMULATE_KEY_HOLD_REPEAT
        )

        return self.async_create_entry(
            title=device_name or unique_id,
            data=data,
            options={
                CONF_KEY_TYPES: key_types,
                CONF_EMULATE_KEY_HOLD: emulate_hold,
                CONF_EMULATE_KEY_HOLD_DELAY: emulate_delay,
                CONF_EMULATE_KEY_HOLD_REPEAT: emulate_repeat,
            },
        )


class KeyboardRemoteOptionsFlow(OptionsFlowWithReload):
    """Handle options for a Keyboard Remote device."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        device_path = self.config_entry.data.get(CONF_DEVICE_PATH, "")

        return self.async_show_form(
            step_id="init",
            description_placeholders={"device_path": device_path},
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_KEY_TYPES): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    selector.SelectOptionDict(
                                        value="key_up", label="Key up"
                                    ),
                                    selector.SelectOptionDict(
                                        value="key_down", label="Key down"
                                    ),
                                    selector.SelectOptionDict(
                                        value="key_hold", label="Key hold"
                                    ),
                                ],
                                multiple=True,
                                mode=selector.SelectSelectorMode.LIST,
                            )
                        ),
                        vol.Required(
                            CONF_EMULATE_KEY_HOLD,
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EMULATE_KEY_HOLD_DELAY,
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0.01,
                                max=5.0,
                                step=0.001,
                                unit_of_measurement="s",
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Required(
                            CONF_EMULATE_KEY_HOLD_REPEAT,
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0.001,
                                max=1.0,
                                step=0.001,
                                unit_of_measurement="s",
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                    }
                ),
                self.config_entry.options,
            ),
        )
