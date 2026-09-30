"""Config flow for Keyboard Remote."""

from collections.abc import Container
from contextlib import suppress
import logging
import math
import os
from typing import Any, NamedTuple, override

import probatio

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.typing import UNDEFINED

from . import list_input_devices
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

    YAML takes any number, and a value outside the form's range would make the
    options form reject its own pre-filled value. NaN falls back to the low end.
    """
    clamped = min(max(value, low), high) if not math.isnan(value) else low
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
    stays part of the ID. Without a uniq only the name is left.
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


def _by_id_links() -> dict[str, str]:
    """Map each event node to its /dev/input/by-id link."""
    links: dict[str, str] = {}
    with suppress(OSError), os.scandir(DEVINPUT_BY_ID) as entries:
        for entry in entries:
            if entry.is_symlink():
                links[os.path.realpath(entry.path)] = entry.path
    return links


class _FoundDevice(NamedTuple):
    """A device the user step can offer."""

    option: selector.SelectOptionDict
    # The unique ID an entry for the device gets
    unique_id: str
    name: str
    linked: bool


def _scan_input_devices_sync() -> list[_FoundDevice]:
    """List input devices to offer, by their by-id link where they have one.

    udev creates no by-id link for Bluetooth devices. Those are offered by
    their event node, once per uniq and name. Only devices that can send keys
    are offered, and host-bus devices, such as the ACPI power button or GPIO
    IR receivers, are left out, since grabbing the system's own buttons would
    take them away from it.
    """
    from evdev import InputDevice, ecodes  # noqa: PLC0415

    links = _by_id_links()
    by_id_devices: list[_FoundDevice] = []
    unlinked_devices: list[_FoundDevice] = []
    unlinked_ids: set[str] = set()
    for dev_path in sorted(list_input_devices()):
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
                _FoundDevice(
                    selector.SelectOptionDict(
                        value=link, label=f"{name} ({unique_id})"
                    ),
                    unique_id,
                    name,
                    linked=True,
                )
            )
        elif (unique_id := _unlinked_unique_id(name, uniq)) not in unlinked_ids:
            unlinked_ids.add(unique_id)
            unlinked_devices.append(
                _FoundDevice(
                    selector.SelectOptionDict(
                        value=dev_path,
                        label=f"{name} ({uniq or os.path.basename(dev_path)})",
                    ),
                    unique_id,
                    name,
                    linked=False,
                )
            )

    by_id_devices.sort(key=lambda device: device.option["value"])
    return by_id_devices + unlinked_devices


def _available_devices_sync(
    configured_ids: Container[str],
    configured_paths: list[str],
    name_matched: Container[str],
) -> tuple[bool, list[selector.SelectOptionDict]]:
    """Scan for devices and drop the ones already configured.

    Returns whether any device was found, and the devices left to offer.
    Besides by unique ID, a device counts as configured when an entry imported
    from YAML before its by-id link existed points at its node, or when an
    entry matched by name alone would match it and it has no by-id link.
    """
    devices = _scan_input_devices_sync()
    configured = {os.path.realpath(path) for path in configured_paths}
    return bool(devices), [
        device.option
        for device in devices
        if device.unique_id not in configured_ids
        and os.path.realpath(device.option["value"]) not in configured
        and (device.linked or device.name not in name_matched)
    ]


def _resolve_yaml_device(
    descriptor: str | None, name: str | None
) -> tuple[str | None, str | None, str | None]:
    """Resolve a YAML device to (device_path, device_name, unique_id).

    unique_id is the by-id link's basename when the device has a stable one,
    or None, in which case the caller falls back to the YAML identity. The
    name is None when the device cannot be opened.
    """
    if descriptor:
        real_path = os.path.realpath(descriptor)
        identity = _get_device_identity(real_path)
        dev_name = identity[0] if identity else None
        if descriptor.startswith(f"{DEVINPUT_BY_ID}/"):
            return (descriptor, dev_name, os.path.basename(descriptor))
        # A by-path or custom udev link already names the device stably, and
        # tells apart identical devices that share one by-id link
        if real_path != descriptor:
            return (descriptor, dev_name, None)
        if (link := _by_id_links().get(real_path)) is not None:
            return (link, dev_name, os.path.basename(link))
        return (descriptor, dev_name, None)

    matches = [
        dev_path
        for dev_path in list_input_devices()
        if (identity := _get_device_identity(dev_path)) and identity[0] == name
    ]
    # A composite keyboard can report the same name on several nodes.
    # Promoting one of them to its by-id path would lock the entry to
    # whichever node was listed first, so keep it name-based.
    if len(matches) == 1 and (link := _by_id_links().get(os.path.realpath(matches[0]))):
        return (link, name, os.path.basename(link))
    return (None, name, None)


class KeyboardRemoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Keyboard Remote."""

    VERSION = 1

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
                title = dev_name
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
                        title = f"{dev_name} ({uniq})"
                return self.async_create_entry(
                    title=title,
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
        name_matched = {
            entry.data[CONF_DEVICE_NAME]
            for entry in entries
            if not entry.data.keys()
            & {CONF_DEVICE_PATH, CONF_DEVICE_DESCRIPTOR, CONF_DEVICE_UNIQ}
        }
        found, available_devices = await self.hass.async_add_executor_job(
            _available_devices_sync, configured_ids, configured_paths, name_matched
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
        """Import a single device from YAML configuration.

        Runs on every start while the YAML is present, with the device plugged
        in or not, so an entry this YAML block created before is looked up by
        the YAML identity first, before the device is resolved.
        """
        # One of the two is set, the schema makes sure
        descriptor: str | None = import_data.get(CONF_DEVICE_DESCRIPTOR)
        name: str | None = import_data.get(CONF_DEVICE_NAME)
        existing = self._async_imported_entry(descriptor, name)
        device_path, device_name, unique_id = await self.hass.async_add_executor_job(
            _resolve_yaml_device, descriptor, name
        )
        if existing is not None:
            return self._async_adopt_or_abort(
                existing, descriptor, device_path, device_name, unique_id
            )

        # The name is unknown while the device is unplugged, so the YAML
        # identity stands in for it
        device_name = device_name or descriptor or name
        if unique_id is None:
            if descriptor:
                unique_id = descriptor
                device_path = device_path or descriptor
            else:
                assert name
                unique_id = name
                device_name = name
                # Without a single by-id link the only path is a bare
                # /dev/input/eventN, which the kernel may hand to a different
                # device after a reboot. Store no path so this entry keeps
                # matching on the name the user configured.
                device_path = None

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        data: dict[str, Any] = {CONF_DEVICE_NAME: device_name}
        if device_path:
            data[CONF_DEVICE_PATH] = device_path
        # Reported in events, and rules out matching the entry by name
        if descriptor:
            data[CONF_DEVICE_DESCRIPTOR] = descriptor

        key_types = import_data[CONF_TYPE]
        if not key_types:
            _LOGGER.warning(
                "Imported %s lists no key types, using %s", CONF_TYPE, DEFAULT_KEY_TYPES
            )
            key_types = DEFAULT_KEY_TYPES
        return self.async_create_entry(
            title=device_name or unique_id,
            data=data,
            options={
                CONF_KEY_TYPES: key_types,
                CONF_EMULATE_KEY_HOLD: import_data[CONF_EMULATE_KEY_HOLD],
                CONF_EMULATE_KEY_HOLD_DELAY: _clamp_imported(
                    CONF_EMULATE_KEY_HOLD_DELAY,
                    import_data[CONF_EMULATE_KEY_HOLD_DELAY],
                    EMULATE_KEY_HOLD_DELAY_MIN,
                    EMULATE_KEY_HOLD_DELAY_MAX,
                ),
                CONF_EMULATE_KEY_HOLD_REPEAT: _clamp_imported(
                    CONF_EMULATE_KEY_HOLD_REPEAT,
                    import_data[CONF_EMULATE_KEY_HOLD_REPEAT],
                    EMULATE_KEY_HOLD_REPEAT_MIN,
                    EMULATE_KEY_HOLD_REPEAT_MAX,
                ),
            },
        )

    @callback
    def _async_imported_entry(
        self, descriptor: str | None, name: str | None
    ) -> ConfigEntry | None:
        """Return the entry an earlier import of this YAML block created."""
        for entry in self._async_current_entries():
            if entry.source != SOURCE_IMPORT:
                continue
            stored_descriptor = entry.data.get(CONF_DEVICE_DESCRIPTOR)
            if descriptor and stored_descriptor == descriptor:
                return entry
            if name and not stored_descriptor and entry.data[CONF_DEVICE_NAME] == name:
                return entry
        return None

    @callback
    def _async_adopt_or_abort(
        self,
        entry: ConfigEntry,
        descriptor: str | None,
        device_path: str | None,
        device_name: str | None,
        unique_id: str | None,
    ) -> ConfigFlowResult:
        """Move an entry imported before its by-id link existed onto the link.

        That entry is keyed by the raw descriptor or name. Only move it when it
        is still on that fallback identity, the by-id ID is free, and the
        device now found is the one it was created for: its name matches, or
        was unknown because the device was unplugged at the first import.
        """
        if (
            unique_id is None
            or entry.unique_id not in (descriptor, device_name)
            or self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, unique_id
            )
            or entry.data[CONF_DEVICE_NAME] not in (descriptor, device_name)
        ):
            return self.async_abort(reason="already_configured")
        data_updates: dict[str, Any] = {CONF_DEVICE_PATH: device_path}
        if device_name:
            data_updates[CONF_DEVICE_NAME] = device_name
        # The startup scan may already have run with the old identity, and
        # nothing rescans a loaded entry when only its data changes.
        return self.async_update_reload_and_abort(
            entry,
            unique_id=unique_id,
            # The first import titled the entry with its fallback name. Replace
            # that, but keep a title the user has since changed.
            title=(
                device_name
                if device_name and entry.title == entry.data[CONF_DEVICE_NAME]
                else UNDEFINED
            ),
            data_updates=data_updates,
            reason="already_configured",
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
