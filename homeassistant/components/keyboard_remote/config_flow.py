"""Config flow for Keyboard Remote."""

import logging
import os
from typing import Any, override

import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.typing import UNDEFINED

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
    name = dev.name
    dev.close()
    return name


def _scan_input_devices_sync() -> list[selector.SelectOptionDict]:
    """Scan /dev/input/by-id/ and return selectable device options."""
    from evdev import InputDevice  # noqa: PLC0415

    options: list[selector.SelectOptionDict] = []

    if not os.path.isdir(DEVINPUT_BY_ID):
        return options

    try:
        entries = sorted(os.scandir(DEVINPUT_BY_ID), key=lambda e: e.name)
    except OSError:
        return options

    for entry in entries:
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


def _exclude_configured_devices(
    devices: list[selector.SelectOptionDict], configured_paths: list[str]
) -> list[selector.SelectOptionDict]:
    """Drop devices whose node an existing entry already points at.

    An entry imported from YAML before its by-id link existed is keyed by the
    raw path, so the by-id basename alone does not show it as configured.
    """
    configured = {os.path.realpath(path) for path in configured_paths}
    return [d for d in devices if os.path.realpath(d["value"]) not in configured]


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
        try:
            with os.scandir(DEVINPUT_BY_ID) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        by_id_map[os.path.realpath(entry.path)] = entry.path
        except OSError:
            pass

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
        matches: list[str] = []
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
                matches.append(dev_path)
        # A composite keyboard can report the same name on several nodes.
        # Promoting one of them to its by-id path would lock the entry to
        # whichever node list_devices returned first, so keep it name-based.
        if len(matches) == 1:
            dev_path = matches[0]
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
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> KeyboardRemoteOptionsFlow:
        """Get the options flow for this handler."""
        return KeyboardRemoteOptionsFlow()

    @override
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

        entries = self._async_current_entries()
        configured_ids = {entry.unique_id for entry in entries}
        configured_paths = [
            path
            for entry in entries
            for key in (CONF_DEVICE_PATH, CONF_DEVICE_DESCRIPTOR)
            if (path := entry.data.get(key))
        ]
        available_devices = await self.hass.async_add_executor_job(
            _exclude_configured_devices,
            [
                d
                for d in available_devices
                if os.path.basename(d["value"]) not in configured_ids
            ],
            configured_paths,
        )

        if not available_devices:
            return self.async_abort(reason="all_devices_configured")

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_DEVICE_PATH): selector.SelectSelector(
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
                device_name = raw_name
                # Without a by-id link the resolved path is a bare
                # /dev/input/eventN, which the kernel may hand to a different
                # device after a reboot. Store no path so this entry keeps
                # matching on the name the user configured.
                device_path = None
            else:
                return self.async_abort(reason="cannot_identify_device")

        # An earlier import of this same YAML block may have run while no by-id
        # symlink existed and fallen back to the raw descriptor or name as its
        # unique ID. Adopt that entry rather than creating a second one.
        legacy_ids = {
            value
            for value in (
                import_data.get("device_descriptor"),
                import_data.get("device_name"),
            )
            if value and value != unique_id
        }
        for entry in self._async_current_entries():
            if entry.unique_id not in legacy_ids:
                continue
            # The device was added again through the UI under its by-id ID.
            # Renaming this entry would give two entries the same unique ID.
            if self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, unique_id
            ):
                return self.async_abort(reason="already_configured")
            # The startup scan may already have run with the old identity, and
            # nothing rescans a loaded entry when only its data changes.
            data_updates: dict[str, Any] = {}
            if device_path:
                data_updates[CONF_DEVICE_PATH] = device_path
            if device_name:
                data_updates[CONF_DEVICE_NAME] = device_name
            return self.async_update_reload_and_abort(
                entry,
                unique_id=unique_id,
                # The first import titled the entry with its fallback name.
                # Replace that, but keep a title the user has since changed.
                title=(
                    device_name
                    if device_name and entry.title == entry.data.get(CONF_DEVICE_NAME)
                    else UNDEFINED
                ),
                data_updates=data_updates,
                reason="already_configured",
            )

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Build entry data
        data: dict[str, Any] = {}
        if device_path:
            data[CONF_DEVICE_PATH] = device_path
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
                probatio.Schema(
                    {
                        probatio.Required(CONF_KEY_TYPES): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=["key_up", "key_down", "key_hold"],
                                multiple=True,
                                translation_key=CONF_KEY_TYPES,
                                mode=selector.SelectSelectorMode.LIST,
                            )
                        ),
                        probatio.Required(
                            CONF_EMULATE_KEY_HOLD,
                        ): selector.BooleanSelector(),
                        probatio.Required(
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
                        probatio.Required(
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
