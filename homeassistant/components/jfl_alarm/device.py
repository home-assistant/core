"""The device tree, and keeping it in step with a panel that introduces itself late.

Home Assistant reads an entity's `device_info` once, when the entity is added. Entities here are
created before any panel has connected, so the registry is updated explicitly when the connection
frame arrives — `async_refresh_panel_device`. This module is separate from `entity.py` so that the
coordinator can call it without importing the entity layer, which imports the coordinator.
"""

from typing import TYPE_CHECKING, Any

from pyjfl import UNKNOWN_MODEL

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)

from .const import DOMAIN, LOGGER, MANUFACTURER

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pyjfl import ConnectionInfo

# `ChildDeviceInfo` and `async_get_device_id_by_identifier` land in Home Assistant 2026.9; `main`
# already carries them (which is what a core PR is reviewed against), but every released version
# this integration actually runs on today — 2026.8.1 included — only has `via_device`. Detected
# once at import time rather than per call, so the two code paths below never disagree mid-run.
try:
    from homeassistant.helpers.device_registry import ChildDeviceInfo as _  # noqa: F401

    _HAS_CHILD_DEVICE_INFO = True
except ImportError:  # pragma: no cover — depends on which HA version is installed
    _HAS_CHILD_DEVICE_INFO = False


def panel_device_id(serial: str) -> str:
    """Return the device registry identifier of a panel.

    Derived from the serial and nothing else, so the device survives removing and re-adding the
    integration.
    """
    return serial


def partition_device_id(serial: str, number: int) -> str:
    """Return the device registry identifier of one partition sub-device."""
    return f"{serial}-partition{number}"


@callback
def build_panel_device(
    info: ConnectionInfo | None, serial: str, name: str
) -> DeviceInfo:
    """Describe the panel itself.

    Everything an installer would otherwise be tempted to expose as a sensor goes here. Firmware
    `"760"` is rendered `7.60`: it is a version, and Home Assistant sorts and displays it as one.

    *name* is the **subentry title**, not the model name, and that is not a cosmetic choice. Panel
    entities are created before the panel has dialled in, and Home Assistant derives an entity's
    `entity_id` from the device name *once*, at registration. Naming the device after the model
    would leave every entity on the panel called `sensor.unknown_jfl_panel_*` for ever.
    """
    spec = info.spec if info is not None else UNKNOWN_MODEL
    device = DeviceInfo(
        identifiers={(DOMAIN, panel_device_id(serial))},
        manufacturer=MANUFACTURER,
        name=name,
        model=spec.name,
        serial_number=serial,
    )
    if info is None:
        return device
    device["model_id"] = f"0x{info.model_byte:02X}"
    if info.firmware:
        device["sw_version"] = render_firmware(info.firmware)
    if info.mac:
        device["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(info.mac))}
    if info.hardware_version:
        # The board revision, from the `0x43` login tail rather than the `0x21` frame. `hw_version`
        # is where an installer expects to read it, beside the firmware.
        device["hw_version"] = info.hardware_version
    return device


def render_firmware(raw: str) -> str:
    """Turn the panel's three-character version field into a version string: `760` -> `7.60`."""
    digits = raw.strip()
    if len(digits) == 3 and digits.isdigit():
        return f"{digits[0]}.{digits[1:]}"
    return digits


def _link_to_panel(hass: HomeAssistant, entry_id: str, serial: str) -> dict[str, Any]:
    """Return the dict fragment that links a sub-device to its panel, on whichever mechanism fits.

    2026.9 replaces `via_device` with `parent_device_id`, a real device id rather than an
    identifier pair — see the `_HAS_CHILD_DEVICE_INFO` note above. The panel is registered
    explicitly in `async_setup_entry`, before any subentry's platforms are forwarded, specifically
    so the 2026.9 lookup never has to tolerate the panel not existing yet; `via_device` never
    needed that guarantee, because it re-resolves the pair every time the registry is read.
    """
    if _HAS_CHILD_DEVICE_INFO:
        return {
            "parent_device_id": dr.async_get_device_id_by_identifier(
                hass, (DOMAIN, panel_device_id(serial)), config_entry_id=entry_id
            )
        }
    return {"via_device": (DOMAIN, panel_device_id(serial))}


def get_sub_device(
    hass: HomeAssistant, entry_id: str, identifier: tuple[str, str]
) -> object | None:
    """Return the sub-device registered under *identifier*, or `None`.

    On 2026.9+, a partition/zone/fence device is a *child* device, and `DeviceRegistry.
    async_get_device` — the lookup that worked before — is deprecated for exactly that reason: it
    only searches main devices, so it always returns `None` for one of these. Exported (not
    prefixed `_`) so tests asserting on a sub-device's registry entry share this same
    version-aware lookup rather than each re-implementing the branch.
    """
    registry = dr.async_get(hass)
    if _HAS_CHILD_DEVICE_INFO:
        return registry.async_get_child_device_by_identifier(identifier, entry_id)
    return registry.async_get_device(identifiers={identifier})


def _sub_device_exists(
    hass: HomeAssistant, entry_id: str, identifier: tuple[str, str]
) -> bool:
    """Whether the sub-device registered under *identifier* already exists.

    `async_apply_programmed_names` uses this rather than `get_sub_device` directly only because a
    bare boolean is what it needs; the deprecation this works around is documented there.
    """
    return get_sub_device(hass, entry_id, identifier) is not None


def _register_sub_device(
    hass: HomeAssistant, *, entry_id: str, subentry_id: str, device: dict[str, Any]
) -> None:
    """Write *device* (a partition/zone/fence built by one of the `build_*_device` helpers).

    `DeviceRegistry.async_get_or_create` is main-device-only from 2026.9 on — it raises on a dict
    carrying `parent_device_id`, which every sub-device built with `_link_to_panel` does on that
    version. `entity_platform.py` makes the same `parent_device_id is not None` check before
    picking `async_get_or_create_child` for a plain entity's `device_info`; this mirrors it for the
    registry writes `async_apply_programmed_names` makes directly, outside that entity path.
    """
    registry = dr.async_get(hass)
    if device.get("parent_device_id") is not None:
        registry.async_get_or_create_child(
            config_entry_id=entry_id,
            config_subentry_id=subentry_id,
            **device,
        )
    else:
        registry.async_get_or_create(
            config_entry_id=entry_id, config_subentry_id=subentry_id, **device
        )


@callback
def build_partition_device(
    hass: HomeAssistant, entry_id: str, serial: str, number: int, *, name: str = ""
) -> dict[str, Any]:
    """Describe one partition as a sub-device of the panel.

    Named through `translation_key` rather than with a literal, so a Brazilian installation reads
    "Partição 1" and not "Partition 1". The alarm entity on this device sets `_attr_name = None`
    and takes the device's name, so this is the only place that name is decided.

    *name* is the partition's programmed name, once the programming read has fetched it. That one is
    a literal, and rightly: it is the installer's own word, in the installer's own language, and
    there is nothing to translate.
    """
    device: dict[str, Any] = {
        "identifiers": {(DOMAIN, partition_device_id(serial, number))},
        **_link_to_panel(hass, entry_id, serial),
    }
    if not _HAS_CHILD_DEVICE_INFO:
        # No `model` on a child device (see build_zone_device's docstring) — but a partition never
        # had one anyway, so the pre-2026.9 path keeps the manufacturer field it always had.
        device["manufacturer"] = MANUFACTURER
    if name:
        device["name"] = name
    else:
        device["translation_key"] = "partition"
        device["translation_placeholders"] = {"number": str(number)}
    return device


@callback
def async_apply_programmed_names(
    hass: HomeAssistant,
    *,
    entry_id: str,
    subentry_id: str,
    serial: str,
    partitions: Mapping[int, str],
) -> None:
    """Write the panel's own names onto the partition devices.

    **The device registry has to be told; `DeviceInfo` is read once and never again.** Every zone
    device was created before the programming was read, so this is the same problem — and the same
    solution — as the panel's model arriving late in `async_refresh_panel_device`.

    **Through `async_get_or_create`, not `async_update_device`, and that is the whole trick.** Only
    the former resolves a `translation_key` into a name; the latter takes a literal. Writing a
    literal here is what produced `Zone 8 A-D ECR` — an English word — in a Portuguese interface,
    on a device that had until then correctly read *Zona 8*.

    A partition that has a name is written literally, because that name is the installer's own
    word and there is nothing to translate; one with no programmed name falls back to the numbered
    translation key.

    `entity_id`s do not move: Home Assistant derives one from the device name once, at
    registration, so only the friendly name changes. A test holds that.
    """
    for number, name in partitions.items():
        if not _sub_device_exists(
            hass, entry_id, (DOMAIN, partition_device_id(serial, number))
        ):
            continue
        _register_sub_device(
            hass,
            entry_id=entry_id,
            subentry_id=subentry_id,
            device=build_partition_device(hass, entry_id, serial, number, name=name),
        )


@callback
def async_refresh_panel_device(
    hass: HomeAssistant,
    *,
    entry_id: str,
    subentry_id: str,
    info: ConnectionInfo,
    name: str,
) -> None:
    """Write the panel's real identity into the device registry.

    Called when the `0x21` frame arrives, which is the first moment the model byte, the firmware
    version and the MAC address are known — and which is always *after* the entities were created.
    Without this the device page reads "Unknown JFL panel" with no firmware for the life of the
    installation, because `device_info` is never looked at again.
    """
    device = build_panel_device(info, info.serial, name)
    LOGGER.debug(
        "%s: updating the device registry with model %s (0x%02X), firmware %s",
        info.serial,
        info.spec.name,
        info.model_byte,
        info.firmware,
    )
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry_id,
        config_subentry_id=subentry_id,
        **device,
    )
