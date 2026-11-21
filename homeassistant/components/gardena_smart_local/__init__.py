"""The GARDENA smart local integration."""

import logging
from types import MappingProxyType

import aiohttp
from gardena_smart_local_api.client import AuthenticationError, RequestError

from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
    ConfigEntryState,
    ConfigSubentry,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType

from .const import CONF_FINGERPRINT, CONF_KNOWN_DEVICES, CONF_PENDING_EXCLUSIONS, DOMAIN
from .coordinator import (
    SUPPORTED_DEVICE_CLASSES,
    GardenaSmartLocalConfigEntry,
    GardenaSmartLocalCoordinator,
)
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.VALVE,
]
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def _async_exclude_and_report_failure(
    hass: HomeAssistant, coordinator: GardenaSmartLocalCoordinator, device_id: str
) -> bool:
    """Exclude a device the user removed from Home Assistant.

    Home Assistant has already deleted the subentry by the time this runs, so
    a failed exclusion cannot block that removal. Warn the user instead: the
    device may still be paired on the gateway even though it is gone from HA.
    """
    if await coordinator.async_exclude_device(device_id):
        # A still-paired device comes back after a failed exclusion; removing
        # it again successfully resolves the earlier warning.
        ir.async_delete_issue(hass, DOMAIN, f"exclude_failed_{device_id}")
        return True
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"exclude_failed_{device_id}",
        config_entry_id=coordinator.config_entry.entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="exclude_failed",
        translation_placeholders={"device_id": device_id},
    )
    return False


def _device_ids(entry: ConfigEntry) -> list[str]:
    """Return the device ids of the device subentries of an entry."""
    return sorted(
        subentry.data["device_id"]
        for subentry in entry.subentries.values()
        if "device_id" in subentry.data
    )


@callback
def _async_exclude_devices_removed_since_last_check(
    hass: HomeAssistant, entry: GardenaSmartLocalConfigEntry
) -> None:
    """Exclude the devices whose subentry is gone since the last check.

    The devices are stored in the entry, so a subentry deleted while the
    integration is not set up, for example because the entry is disabled,
    is noticed on the next setup.
    """
    known = entry.data.get(CONF_KNOWN_DEVICES, [])
    current = _device_ids(entry)
    if known == current:
        return
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_KNOWN_DEVICES: current}
    )
    for device_id in known:
        if device_id not in current:
            _async_exclude_removed_device(hass, entry, device_id)


@callback
def _async_exclude_removed_device(
    hass: HomeAssistant, entry: GardenaSmartLocalConfigEntry, device_id: str
) -> None:
    """Exclude a device whose subentry the user removed."""
    # The removal is stored before anything is sent, so an exclusion that has
    # to wait for the gateway, or that an unload interrupts, runs on the next
    # setup. Until then the device must not get a new subentry from discovery.
    pending = entry.data.get(CONF_PENDING_EXCLUSIONS, [])
    if device_id not in pending:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_PENDING_EXCLUSIONS: [*pending, device_id]}
        )
    if entry.state is ConfigEntryState.LOADED:
        entry.async_create_background_task(
            hass,
            _async_exclude_pending_device(hass, entry, device_id),
            f"gardena_exclude_{device_id}",
        )


async def _async_exclude_pending_device(
    hass: HomeAssistant, entry: GardenaSmartLocalConfigEntry, device_id: str
) -> None:
    """Exclude a device the user removed and drop it from the pending list."""
    coordinator = entry.runtime_data
    excluded = await _async_exclude_and_report_failure(hass, coordinator, device_id)
    pending = list(entry.data.get(CONF_PENDING_EXCLUSIONS, []))
    if device_id in pending:
        pending.remove(device_id)
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_PENDING_EXCLUSIONS: pending}
        )
    if not excluded:
        # A failure is reported like any other one: the device is still
        # paired, so it gets its subentry back and the user can remove it again.
        coordinator.async_update_listeners()


async def _async_exclude_pending_devices(
    hass: HomeAssistant, entry: GardenaSmartLocalConfigEntry
) -> None:
    """Exclude the devices removed while the entry was not loaded."""
    for device_id in list(entry.data.get(CONF_PENDING_EXCLUSIONS, [])):
        await _async_exclude_pending_device(hass, entry, device_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the GARDENA smart local integration."""
    async_setup_services(hass)

    @callback
    def _on_entry_changed(change_type: ConfigEntryChange, entry: ConfigEntry) -> None:
        if entry.domain != DOMAIN or change_type is ConfigEntryChange.REMOVED:
            return
        _async_exclude_devices_removed_since_last_check(hass, entry)

    async_dispatcher_connect(hass, SIGNAL_CONFIG_ENTRY_CHANGED, _on_entry_changed)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GardenaSmartLocalConfigEntry
) -> None:
    """Set up GARDENA smart local from a config entry."""
    _async_exclude_devices_removed_since_last_check(hass, entry)
    coordinator = GardenaSmartLocalCoordinator(
        hass,
        entry,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        password=entry.data[CONF_PASSWORD],
        fingerprint=entry.data[CONF_FINGERPRINT],
    )
    # Registered first, so a cancelled or failed setup closes the connection too.
    entry.async_on_unload(coordinator.async_disconnect)
    try:
        await coordinator.async_connect()
    except Exception as err:
        if isinstance(err, AuthenticationError):
            raise ConfigEntryAuthFailed(
                "The GARDENA smart Gateway rejected the configured password"
            ) from err
        if isinstance(err, aiohttp.ServerFingerprintMismatch):
            raise ConfigEntryError(
                "The certificate of the GARDENA smart Gateway changed. Reconfigure "
                "the integration to trust the new certificate"
            ) from err
        if isinstance(err, (aiohttp.ClientError, OSError, TimeoutError, RequestError)):
            raise ConfigEntryNotReady(
                f"Could not connect to GARDENA smart Gateway at {coordinator.uri}"
            ) from err
        # Anything else is a defect; retrying forever would only hide it.
        raise
    entry.runtime_data = coordinator

    async def _stop(_event: object) -> None:
        await coordinator.async_disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop))

    @callback
    def _ensure_device_subentries() -> None:
        if not coordinator.data:
            return
        pending = entry.data.get(CONF_PENDING_EXCLUSIONS, [])
        subentry_device_ids = {
            se.data["device_id"]
            for se in entry.subentries.values()
            if "device_id" in se.data
        }
        for device in coordinator.data.values():
            if not isinstance(device, SUPPORTED_DEVICE_CLASSES):
                # Sensors, mowers, pumps etc. have no entity in this valve-only
                # integration; a subentry for them would be empty.
                continue
            if device.id in subentry_device_ids or device.id in pending:
                continue
            subentry = ConfigSubentry(
                data=MappingProxyType({"device_id": device.id}),
                subentry_type="device",
                title=f"{device.model_definition.name} {device.serial_number}",
                unique_id=device.id,
            )
            hass.config_entries.async_add_subentry(entry, subentry)
            _LOGGER.info("Created subentry for device %s", device.id)

    # Register before platform listeners so subentries exist when
    # platforms look them up for newly discovered devices.
    entry.async_on_unload(coordinator.async_add_listener(_ensure_device_subentries))
    _ensure_device_subentries()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if entry.data.get(CONF_PENDING_EXCLUSIONS):
        entry.async_create_background_task(
            hass,
            _async_exclude_pending_devices(hass, entry),
            "gardena_exclude_pending",
        )


async def async_unload_entry(
    hass: HomeAssistant, entry: GardenaSmartLocalConfigEntry
) -> None:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unload_failed",
        )
