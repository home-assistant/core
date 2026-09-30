"""Config flow for Keyboard Remote."""

from collections.abc import Container
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
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.typing import UNDEFINED

from .const import (
    CONF_DEVICE_DESCRIPTOR,
    CONF_DEVICE_NAME,
    CONF_DEVICE_PATH,
    CONF_DEVICE_UNIQ,
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
    EMULATE_KEY_HOLD_DELAY_MAX,
    EMULATE_KEY_HOLD_DELAY_MIN,
    EMULATE_KEY_HOLD_REPEAT_MAX,
    EMULATE_KEY_HOLD_REPEAT_MIN,
)

_LOGGER = logging.getLogger(__name__)


def _clamp_imported(key: str, value: float, low: float, high: float) -> float:
    """Fit an imported YAML value into the range the options form accepts.

    YAML accepted any number, and a value outside the form's range would make
    the options form reject its own pre-filled value.
    """
    clamped = min(max(value, low), high)
    if clamped != value:
        _LOGGER.warning(
            "Imported %s of %s is outside %s to %s, using %s",
            key,
            value,
            low,
            high,
            clamped,
        )
    return clamped


def _unlinked_unique_id(name: str, uniq: str) -> str:
    """Return the unique ID of a device that has no by-id link.

    The uniq of a Bluetooth device is its own address, which tells identical
    remotes apart. The nodes of one composite device share it, so the name
    stays part of the ID. Without a uniq, as for GPIO IR receivers, only the
    name is left.
    """
    return f"{uniq} {name}" if uniq else name


def _get_device_identity(device_path: str) -> tuple[str, str] | None:
    """Open an input device and return its name and uniq, or None on error."""
    from evdev import InputDevice  # noqa: PLC0415

    try:
        dev = InputDevice(os.path.realpath(device_path))
    except OSError:
        return None
    identity = (dev.name, dev.uniq)
    dev.close()
    return identity


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


def _by_id_links() -> dict[str, str]:
    """Map each event node to its /dev/input/by-id link."""
    links: dict[str, str] = {}
    if os.path.isdir(DEVINPUT_BY_ID):
        try:
            with os.scandir(DEVINPUT_BY_ID) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        links[os.path.realpath(entry.path)] = entry.path
        except OSError:
            pass
    return links


def _scan_input_devices_sync() -> list[tuple[selector.SelectOptionDict, str]]:
    """List input devices to offer, by their by-id link where they have one.

    Each device comes with the unique ID an entry for it gets: the by-id link's
    basename, or the device name.

    udev creates no by-id link for Bluetooth devices, nor for devices without
    a bus ID such as GPIO IR receivers. Those are offered by their event node
    and configured by name, once per name. Only devices that can send keys
    are offered, and host-bus devices such as the ACPI power button are left
    out, since grabbing one would take it away from the system.
    """
    from evdev import InputDevice, ecodes, list_devices  # noqa: PLC0415

    links = _by_id_links()
    by_id_devices: list[tuple[selector.SelectOptionDict, str]] = []
    name_devices: list[tuple[selector.SelectOptionDict, str]] = []
    names: set[str] = set()
    for dev_path in sorted(list_devices(DEVINPUT)):
        try:
            dev = InputDevice(dev_path)
        except OSError:
            continue
        name = dev.name
        uniq = dev.uniq
        try:
            usable = (
                ecodes.EV_KEY in dev.capabilities()
                and dev.info.bustype != ecodes.BUS_HOST
            )
        except OSError:
            # Unplugged since it was opened
            continue
        finally:
            dev.close()
        if not usable:
            continue
        if (link := links.get(os.path.realpath(dev_path))) is not None:
            unique_id = os.path.basename(link)
            by_id_devices.append(
                (
                    selector.SelectOptionDict(
                        value=link, label=f"{name} ({unique_id})"
                    ),
                    unique_id,
                )
            )
        elif (unique_id := _unlinked_unique_id(name, uniq)) not in names:
            names.add(unique_id)
            name_devices.append(
                (
                    selector.SelectOptionDict(
                        value=dev_path,
                        label=f"{name} ({uniq or os.path.basename(dev_path)})",
                    ),
                    unique_id,
                )
            )

    by_id_devices.sort(key=lambda device: device[0]["value"])
    return by_id_devices + name_devices


def _available_devices_sync(
    configured_ids: Container[str], configured_paths: list[str]
) -> tuple[bool, list[selector.SelectOptionDict]]:
    """Scan for devices and drop the ones already configured.

    Returns whether any device was found, and the devices left to offer. An
    entry imported from YAML before its by-id link existed is keyed by the raw
    path, so it is matched by node as well as by unique ID.
    """
    devices = _scan_input_devices_sync()
    configured = {os.path.realpath(path) for path in configured_paths}
    return bool(devices), [
        option
        for option, unique_id in devices
        if unique_id not in configured_ids
        and os.path.realpath(option["value"]) not in configured
    ]


def _resolve_yaml_device(
    import_data: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    """Resolve YAML device config to (device_path, device_name, unique_id).

    Returns (None, None, None) if device cannot be resolved at all.
    Returns (path, name, unique_id) where unique_id is the by-id basename
    if available, or None if no by-id symlink can be found.
    """
    from evdev import list_devices  # noqa: PLC0415

    descriptor = import_data.get("device_descriptor")
    name = import_data.get("device_name")

    by_id_map = _by_id_links()

    if descriptor:
        real_path = os.path.realpath(descriptor)
        dev_name = _get_device_name(real_path)
        if real_path in by_id_map:
            by_id_path = by_id_map[real_path]
            return (by_id_path, dev_name, os.path.basename(by_id_path))
        # No by-id symlink; return raw path, no stable unique_id
        return (descriptor, dev_name, None)

    if name:
        matches = [
            dev_path
            for dev_path in list_devices(DEVINPUT)
            if _get_device_name(dev_path) == name
        ]
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
            by_id = device_path.startswith(f"{DEVINPUT_BY_ID}/")
            if by_id:
                await self.async_set_unique_id(os.path.basename(device_path))
                self._abort_if_unique_id_configured()

            identity = await self.hass.async_add_executor_job(
                _get_device_identity, device_path
            )
            if identity is None:
                errors["base"] = "cannot_connect"
            else:
                dev_name, uniq = identity
                data = {CONF_DEVICE_NAME: dev_name}
                if by_id:
                    data[CONF_DEVICE_PATH] = device_path
                else:
                    # Without a by-id link the event node can change when the
                    # device reconnects, so match by uniq and name instead.
                    await self.async_set_unique_id(_unlinked_unique_id(dev_name, uniq))
                    self._abort_if_unique_id_configured()
                    if uniq:
                        data[CONF_DEVICE_UNIQ] = uniq
                return self.async_create_entry(
                    title=dev_name,
                    data=data,
                    options={
                        CONF_KEY_TYPES: DEFAULT_KEY_TYPES,
                        CONF_EMULATE_KEY_HOLD: DEFAULT_EMULATE_KEY_HOLD,
                        CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
                        CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
                    },
                )

        entries = self._async_current_entries()
        configured_ids = {entry.unique_id for entry in entries if entry.unique_id}
        # Not the YAML descriptor: runtime matching ignores it, and its eventN
        # may now belong to an unrelated device.
        configured_paths = [
            path for entry in entries if (path := entry.data.get(CONF_DEVICE_PATH))
        ]
        found, available_devices = await self.hass.async_add_executor_job(
            _available_devices_sync, configured_ids, configured_paths
        )

        if not found:
            return self.async_abort(reason="no_devices")
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

        data: dict[str, Any] = {}
        if device_path:
            data[CONF_DEVICE_PATH] = device_path
        if device_name:
            data[CONF_DEVICE_NAME] = device_name
        # Store original YAML descriptor for runtime matching
        if raw_descriptor := import_data.get("device_descriptor"):
            data[CONF_DEVICE_DESCRIPTOR] = raw_descriptor

        key_types = import_data.get("type", DEFAULT_KEY_TYPES)
        emulate_hold = import_data.get("emulate_key_hold", DEFAULT_EMULATE_KEY_HOLD)
        emulate_delay = _clamp_imported(
            CONF_EMULATE_KEY_HOLD_DELAY,
            import_data.get("emulate_key_hold_delay", DEFAULT_EMULATE_KEY_HOLD_DELAY),
            EMULATE_KEY_HOLD_DELAY_MIN,
            EMULATE_KEY_HOLD_DELAY_MAX,
        )
        emulate_repeat = _clamp_imported(
            CONF_EMULATE_KEY_HOLD_REPEAT,
            import_data.get("emulate_key_hold_repeat", DEFAULT_EMULATE_KEY_HOLD_REPEAT),
            EMULATE_KEY_HOLD_REPEAT_MIN,
            EMULATE_KEY_HOLD_REPEAT_MAX,
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
        errors: dict[str, str] = {}
        if user_input is not None:
            # An entry with no key types would never fire a command event
            if user_input[CONF_KEY_TYPES]:
                return self.async_create_entry(data=user_input)
            errors[CONF_KEY_TYPES] = "no_key_types"

        # Entries matched by name store no path
        data = self.config_entry.data
        device = data.get(CONF_DEVICE_PATH) or data[CONF_DEVICE_NAME]

        return self.async_show_form(
            step_id="init",
            description_placeholders={"device": device},
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
                                min=EMULATE_KEY_HOLD_DELAY_MIN,
                                max=EMULATE_KEY_HOLD_DELAY_MAX,
                                step=0.001,
                                unit_of_measurement="s",
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        probatio.Required(
                            CONF_EMULATE_KEY_HOLD_REPEAT,
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=EMULATE_KEY_HOLD_REPEAT_MIN,
                                max=EMULATE_KEY_HOLD_REPEAT_MAX,
                                step=0.001,
                                unit_of_measurement="s",
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                    }
                ),
                user_input or self.config_entry.options,
            ),
            errors=errors,
        )
