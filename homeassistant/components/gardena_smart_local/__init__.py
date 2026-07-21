"""The GARDENA smart local integration."""

import logging
from types import MappingProxyType

from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
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
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .coordinator import GardenaSmartLocalCoordinator

PLATFORMS: list[Platform] = [
    Platform.VALVE,
]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GARDENA smart local from a config entry."""
    coordinator = GardenaSmartLocalCoordinator(
        hass,
        entry,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        password=entry.data[CONF_PASSWORD],
    )
    try:
        await coordinator.async_connect()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Could not connect to GARDENA smart Gateway at {coordinator.uri}"
        ) from err
    entry.runtime_data = coordinator

    async def _stop(_event: object) -> None:
        await coordinator.async_disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop))

    @callback
    def _ensure_device_subentries() -> None:
        if not coordinator.data:
            return
        dev_reg = dr.async_get(hass)
        subentry_ids_by_device = {
            se.data["device_id"]: sid
            for sid, se in entry.subentries.items()
            if "device_id" in se.data
        }
        for device in coordinator.data.values():
            subentry_id = subentry_ids_by_device.get(device.id)
            if subentry_id is None:
                subentry = ConfigSubentry(
                    data=MappingProxyType({"device_id": device.id}),
                    subentry_type="device",
                    title=f"{device.model_definition.name} {device.serial_number}",
                    unique_id=device.id,
                )
                hass.config_entries.async_add_subentry(entry, subentry)
                subentry_id = subentry.subentry_id
                _LOGGER.info("Created subentry for device %s", device.id)

            # TODO remove this re-link migration after a few releases, once we  # pylint: disable=fixme
            # can be sure most users have migrated to the new config entries
            # structure with subentries.
            dev_entry = dev_reg.async_get_device(identifiers={(DOMAIN, device.id)})
            if (
                dev_entry is not None
                and None
                in dev_entry.config_entries_subentries.get(entry.entry_id, set())
            ):
                dev_reg.async_update_device(
                    dev_entry.id,
                    add_config_entry_id=entry.entry_id,
                    add_config_subentry_id=subentry_id,
                    remove_config_entry_id=entry.entry_id,
                    remove_config_subentry_id=None,
                )
                _LOGGER.info("Migrated device %s to subentry", device.id)

    # Register before platform listeners so subentries exist when
    # platforms look them up for newly discovered devices.
    entry.async_on_unload(coordinator.async_add_listener(_ensure_device_subentries))
    _ensure_device_subentries()

    known_subentries: dict[str, str] = {
        sid: se.data["device_id"]
        for sid, se in entry.subentries.items()
        if "device_id" in se.data
    }

    @callback
    def _on_entry_updated(
        change_type: ConfigEntryChange, changed_entry: ConfigEntry
    ) -> None:
        if (
            change_type != ConfigEntryChange.UPDATED
            or changed_entry.entry_id != entry.entry_id
        ):
            return
        current_ids = set(entry.subentries.keys())
        for subentry_id, device_id in list(known_subentries.items()):
            if subentry_id not in current_ids:
                del known_subentries[subentry_id]
                hass.async_create_background_task(
                    coordinator.async_exclude_device(device_id),
                    f"gardena_exclude_{device_id}",
                )
        for sid, se in entry.subentries.items():
            if sid not in known_subentries and "device_id" in se.data:
                known_subentries[sid] = se.data["device_id"]

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_CONFIG_ENTRY_CHANGED, _on_entry_updated)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    coordinator: GardenaSmartLocalCoordinator = entry.runtime_data
    await coordinator.async_disconnect()
    return True
