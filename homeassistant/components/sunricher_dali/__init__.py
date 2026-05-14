"""The Sunricher DALI integration."""

import asyncio
from collections.abc import Callable, Sequence
from contextlib import suppress
import logging

from packaging.version import InvalidVersion, Version
from PySrDaliGateway import CallbackEventType, DaliGateway, Device
from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
    MANUFACTURER,
    MIN_SUPPORTED_FW_VERSION,
    MIN_SUPPORTED_SW_VERSION,
)
from .types import DaliCenterConfigEntry, DaliCenterData

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.SCENE,
    Platform.SENSOR,
]
_LOGGER = logging.getLogger(__name__)

_MIN_SUPPORTED_SW = Version(MIN_SUPPORTED_SW_VERSION)
_MIN_SUPPORTED_FW = Version(MIN_SUPPORTED_FW_VERSION)


async def _async_cleanup_failed_setup(
    gateway: DaliGateway, unsub_version: Callable[[], None]
) -> None:
    """Clean up resources registered before config entry setup completed."""
    unsub_version()
    with suppress(DaliGatewayError):
        await gateway.disconnect()


def _remove_missing_devices(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    devices: Sequence[Device],
    gateway_identifier: tuple[str, str],
) -> None:
    """Detach devices that are no longer provided by the gateway."""
    device_registry = dr.async_get(hass)
    known_device_ids = {device.dev_id for device in devices}

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if gateway_identifier in device_entry.identifiers:
            continue

        domain_device_ids = {
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        }

        if not domain_device_ids:
            continue

        if domain_device_ids.isdisjoint(known_device_ids):
            device_registry.async_update_device(
                device_entry.id,
                remove_config_entry_id=entry.entry_id,
            )


async def async_setup_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Set up Sunricher DALI from a config entry."""

    gateway = DaliGateway(
        entry.data[CONF_SERIAL_NUMBER],
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        name=entry.data[CONF_NAME],
    )
    gw_sn = gateway.gw_sn

    @callback
    def _handle_version_update(versions: tuple[str, str]) -> None:
        _async_check_firmware_version(hass, entry, gateway, versions)

    unsub_version = gateway.register_listener(
        CallbackEventType.VERSION_UPDATED,
        _handle_version_update,
        gateway.gw_sn,
    )

    try:
        await gateway.connect()
    except DaliGatewayError as exc:
        unsub_version()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from exc

    if gateway.software_version and gateway.firmware_version:
        _async_check_firmware_version(hass, entry, gateway)

    try:
        devices, scenes = await asyncio.gather(
            gateway.discover_devices(),
            gateway.discover_scenes(),
        )
    except DaliGatewayError as exc:
        # async_on_unload only fires after a successful load, so clean up
        # the listener manually before bailing out.
        await _async_cleanup_failed_setup(gateway, unsub_version)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_discover_devices",
        ) from exc

    _LOGGER.debug("Discovered %d devices on gateway %s", len(devices), gw_sn)

    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, gw_sn)},
        identifiers={(DOMAIN, gw_sn)},
        manufacturer=MANUFACTURER,
        name=gateway.name,
        model="SR-GW-EDA",
        serial_number=gw_sn,
    )
    _remove_missing_devices(hass, entry, devices, (DOMAIN, gw_sn))

    entry.runtime_data = DaliCenterData(
        gateway=gateway,
        devices=devices,
        scenes=scenes,
    )
    try:
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    except Exception:
        await _async_cleanup_failed_setup(gateway, unsub_version)
        raise
    entry.async_on_unload(unsub_version)

    return True


@callback
def _async_check_firmware_version(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    gateway: DaliGateway,
    versions: tuple[str, str] | None = None,
) -> None:
    """Raise a repair issue if the gateway firmware is below supported minimums."""
    sw_version, fw_version = versions or (
        gateway.software_version,
        gateway.firmware_version,
    )
    issue_id = f"unsupported_firmware_{entry.entry_id}"

    if not sw_version or not fw_version:
        return

    try:
        sw_parsed = Version(sw_version)
        fw_parsed = Version(fw_version)
    except InvalidVersion:
        _LOGGER.debug(
            "Gateway %s reported unparsable firmware version (sw=%s, fw=%s)",
            gateway.gw_sn,
            sw_version,
            fw_version,
        )
        return

    if sw_parsed < _MIN_SUPPORTED_SW or fw_parsed < _MIN_SUPPORTED_FW:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            is_persistent=True,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key="unsupported_firmware",
            translation_placeholders={
                "sw_version": sw_version,
                "fw_version": fw_version,
                "min_sw_version": MIN_SUPPORTED_SW_VERSION,
                "min_fw_version": MIN_SUPPORTED_FW_VERSION,
            },
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_unload_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        await entry.runtime_data.gateway.disconnect()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> None:
    """Clear persistent repair issues that belong to this entry."""
    ir.async_delete_issue(hass, DOMAIN, f"unsupported_firmware_{entry.entry_id}")
