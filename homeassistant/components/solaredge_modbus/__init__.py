"""Support for SolarEdge inverters over Modbus.

The inverter is a Modbus device. This integration does not own its connection:
it borrows a ``ModbusUnit`` from the ``modbus`` integration, which shares one
connection per device between everything talking to it, and hands that unit to
the ``solaredged`` library.
"""

from collections.abc import Set as AbstractSet
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING

from modbus_connection import ModbusUnit
from solaredged import SolarEdge, SolarEdgeConnectionError, SolarEdgeError

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTACHMENT_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
    SUBSYSTEM_BATTERIES,
    SUBSYSTEM_COMMON,
    SUBSYSTEM_INVERTER,
    SUBSYSTEM_METERS,
)
from .coordinator import (
    SolarEdgeModbusConfigEntry,
    SolarEdgeModbusDataUpdateCoordinator,
    SolarEdgeModbusRuntimeData,
)
from .entity import attachment_identity, inverter_device_info
from .helpers import create_modbus_params

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: SolarEdgeModbusConfigEntry
) -> bool:
    """Set up SolarEdge Modbus from a config entry."""
    serial_number = entry.unique_id
    if TYPE_CHECKING:
        assert serial_number is not None

    try:
        unit = async_get_unit(
            hass, entry, create_modbus_params(entry.data), entry.data[CONF_UNIT_ID]
        )
    except HomeAssistantError as err:
        # The device is already in use over different link settings, which one
        # shared connection cannot honour.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="link_settings_in_use",
            translation_placeholders={"error": str(err)},
        ) from err

    try:
        solaredge = await SolarEdge.async_probe(unit)
    except SolarEdgeConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except SolarEdgeError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_solaredge_device",
        ) from err

    readings = SolarEdgeModbusDataUpdateCoordinator(
        hass,
        entry,
        solaredge,
        poll=solaredge.async_update_readings,
        interval=SCAN_INTERVAL,
        label="readings",
    )
    settings = SolarEdgeModbusDataUpdateCoordinator(
        hass,
        entry,
        solaredge,
        poll=solaredge.async_update_settings,
        interval=SETTINGS_SCAN_INTERVAL,
        label="settings",
    )

    await readings.async_config_entry_first_refresh()

    # Identity arrives with that first read, and a poll can come back without
    # it. Nothing can be checked then, so try again rather than accept the
    # entry: an address or device ID can end up pointing at another inverter (a
    # reused DHCP lease, a changed setting), and every identity here derives
    # from the entry's serial number.
    if SUBSYSTEM_COMMON in readings.data.failed:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="identity_unavailable",
        )

    # The platforms read a component's DID once, so without it the phase
    # entities would stay missing until a reload.
    measuring = {SUBSYSTEM_INVERTER}
    measuring.update(f"meters[{index}]" for index in range(len(solaredge.meters)))
    measuring.update(f"batteries[{index}]" for index in range(len(solaredge.batteries)))
    if measuring & readings.data.failed.keys():
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="measurements_unavailable",
        )

    # Registered up front: a meter sub-device can only name the inverter it
    # hangs off once that device has an ID.
    device_info = inverter_device_info(solaredge, serial_number)
    inverter = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **device_info
    )
    # The readings poll already proved the link; a control block that refuses
    # one read leaves its own entities unavailable instead of failing setup.
    await settings.async_refresh()

    entry.runtime_data = SolarEdgeModbusRuntimeData(
        readings=readings,
        settings=settings,
        device_info=device_info,
        inverter_device_id=inverter.id,
        attachments=_attachment_identities(solaredge),
    )

    if silent := solaredge.unresponsive_blocks & {
        SUBSYSTEM_BATTERIES,
        SUBSYSTEM_METERS,
    }:
        LOGGER.warning(
            "%s did not answer for its %s while probing, so their entities are"
            " missing until it does; reloading probes again",
            entry.title,
            " and ".join(sorted(silent)),
        )

    _async_remove_stale_devices(hass, entry, solaredge, serial_number, silent=silent)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # What is wired to the inverter is read while setting up, so a meter or
    # battery added or removed later needs the entry to load again to be seen.
    entry.async_on_unload(
        async_track_time_interval(
            hass,
            partial(_async_reload_when_attachments_change, hass, entry, unit),
            ATTACHMENT_SCAN_INTERVAL,
        )
    )

    return True


def _attachment_identities(solaredge: SolarEdge) -> frozenset[str]:
    """Return what the meters and batteries attached right now are known by."""
    return frozenset(
        [
            *(
                f"meter_{attachment_identity(meter, index)}"
                for index, meter in enumerate(solaredge.meters, 1)
            ),
            *(
                f"battery_{attachment_identity(battery, index)}"
                for index, battery in enumerate(solaredge.batteries, 1)
            ),
        ]
    )


async def _async_reload_when_attachments_change(
    hass: HomeAssistant,
    entry: SolarEdgeModbusConfigEntry,
    unit: ModbusUnit,
    _now: datetime,
) -> None:
    """Reload the entry when the hardware wired to the inverter changed."""
    solaredge = entry.runtime_data.solaredge

    # Swapping one meter for another leaves the count alone, but the polls have
    # been reading the new one's serial number since it was wired in.
    if _attachment_identities(solaredge) != entry.runtime_data.attachments:
        LOGGER.info(
            "%s: what is attached changed, reloading to pick that up",
            entry.title,
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)
        return

    try:
        probed = await SolarEdge.async_probe(unit)
    except SolarEdgeError as err:
        # Nothing to conclude from a probe that did not finish; the coordinators
        # report an inverter that stopped answering.
        LOGGER.debug("%s: could not probe for attached hardware: %s", entry.title, err)
        return

    for name, found, known in (
        (SUBSYSTEM_METERS, len(probed.meters), len(solaredge.meters)),
        (SUBSYSTEM_BATTERIES, len(probed.batteries), len(solaredge.batteries)),
    ):
        if found == known:
            continue
        # A block that stayed silent is taken for absent, which is not the same
        # as the inverter saying it is gone, and reloading on that would drop a
        # device over one timeout.
        if found < known and name in probed.unresponsive_blocks:
            continue

        LOGGER.info(
            "%s: %s went from %s to %s, reloading to pick that up",
            entry.title,
            name,
            known,
            found,
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)
        return


def _async_remove_stale_devices(
    hass: HomeAssistant,
    entry: SolarEdgeModbusConfigEntry,
    solaredge: SolarEdge,
    serial_number: str,
    *,
    silent: AbstractSet[str],
) -> None:
    """Remove devices for meters and batteries no longer attached.

    A block that stayed silent while probing is taken for absent, and silence
    is not the inverter saying its hardware is gone. Devices of that kind stay
    where they are; the kind that did answer is still cleaned up.
    """
    current = {(DOMAIN, serial_number)}
    current.update(
        (DOMAIN, f"{serial_number}_meter_{attachment_identity(meter, index)}")
        for index, meter in enumerate(solaredge.meters, 1)
    )
    current.update(
        (DOMAIN, f"{serial_number}_battery_{attachment_identity(battery, index)}")
        for index, battery in enumerate(solaredge.batteries, 1)
    )

    unproven = tuple(
        f"{serial_number}_{kind}_"
        for block, kind in (
            (SUBSYSTEM_BATTERIES, "battery"),
            (SUBSYSTEM_METERS, "meter"),
        )
        if block in silent
    )

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if current.intersection(device.identifiers):
            continue
        if any(identifier.startswith(unproven) for _, identifier in device.identifiers):
            continue
        device_registry.async_remove_device(device.id)


async def async_unload_entry(
    hass: HomeAssistant, entry: SolarEdgeModbusConfigEntry
) -> bool:
    """Unload SolarEdge Modbus config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
