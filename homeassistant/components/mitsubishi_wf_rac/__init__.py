"""The Mitsubishi WF-RAC integration."""

import logging

from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_AIRCO_ID,
    CONF_AVAILABILITY_CHECK,
    CONF_AVAILABILITY_RETRY_LIMIT,
    CONF_CONNECTION_METHOD,
    CONF_OPERATOR_ID,
    DOMAIN,
)
from .coordinator import (
    AVAILABILITY_FAILURE_LIMIT_MIN,
    Device,
    MitsubishiWfRacConfigEntry,
    MitsubishiWfRacData,
    registration_full_issue_id,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE]


async def async_migrate_entry(
    hass: HomeAssistant, entry: MitsubishiWfRacConfigEntry
) -> bool:
    """Bring an entry of the custom component that used to own this domain up to date.

    Core never wrote versions 1 to 6; they come from that custom component, and
    an installation switching over brings its entries along. They need one
    normalisation rather than a replay of that history, so any of them reaches
    the same shape in a single step:

    - The host belongs in entry.data. It sat in options so it could be edited
      there, which also meant the discovery helper that refreshes a moved unit
      (_abort_if_unique_id_configured(updates=...)) merged the new address into
      data, where setup never looked - so the address silently stayed stale.
    - The availability toggle goes, along with a retry key nothing ever read.
      The toggle was never a defensible choice: the module reassociates with
      the network about once an hour, so some tolerance is always right, and
      switching it off was arithmetically identical to a limit of 1. The limit
      itself is a real choice on a weak link and stays, floored at what Device
      enforces anyway.
    - Entries added by hand carry no unique id, because the manual step checked
      for a duplicate airco itself instead of registering one. Without it
      zeroconf cannot recognise the entry, so a unit that moved was offered as
      a new discovery. The module announces itself as <mac>.local and the airco
      id is that same MAC, so this is the identity discovery already matches
      on.
    """

    if entry.version < 7:
        data = dict(entry.data)
        options = dict(entry.options)

        if CONF_HOST in options:
            data[CONF_HOST] = options.pop(CONF_HOST)

        options.pop(CONF_AVAILABILITY_CHECK, None)
        options.pop("availability_retry", None)
        options[CONF_AVAILABILITY_RETRY_LIMIT] = max(
            AVAILABILITY_FAILURE_LIMIT_MIN,
            options.get(CONF_AVAILABILITY_RETRY_LIMIT, AVAILABILITY_FAILURE_LIMIT_MIN),
        )

        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            unique_id=data[CONF_AIRCO_ID].lower(),
            version=7,
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MitsubishiWfRacConfigEntry
) -> bool:
    """Establish connection with mitsubishi-wf-rac."""
    device: str = entry.data[CONF_HOST]
    _device = await create_device_from_entry(entry, hass)

    await _device.update()  # initial update to get fresh values
    # update() catches its own errors and reflects them via .available instead
    # of raising (see coordinator.py) - check that instead of try/except so a
    # device that's unreachable at startup gets HA's automatic retry-with-backoff
    # rather than a silently "loaded" entry with no working entities.
    if not _device.available:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"device": device},
        )

    # Persist the discovered connection method (http/https) so we can skip
    # protocol discovery (and its potential extra round-trip) after the next
    # restart. Nothing listens for entry updates, so this does not reload the
    # entry that is still setting up.
    method = _device.connection_method
    if method and entry.data.get(CONF_CONNECTION_METHOD) != method:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_CONNECTION_METHOD: method}
        )
        _LOGGER.debug(
            "Persisted connection method [%s] for device [%s]", method, device
        )

    entry.runtime_data = MitsubishiWfRacData(_device)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def create_device_from_entry(
    entry: MitsubishiWfRacConfigEntry, hass: HomeAssistant
) -> Device:
    """Build the coordinator for a config entry."""
    device: str = entry.data[CONF_HOST]
    name: str = entry.title
    device_id: str = entry.data[CONF_DEVICE_ID]
    operator_id: str = entry.data[CONF_OPERATOR_ID]
    port: int = entry.data[CONF_PORT]
    airco_id: str = entry.data[CONF_AIRCO_ID]
    # Only entries carried over from the custom component that used to own
    # this domain can name a limit; nothing offers to set one here. Floored in
    # Device itself as well as in the migration, so none of them runs with less
    # tolerance than the module needs.
    availability_failure_limit: int = entry.options.get(
        CONF_AVAILABILITY_RETRY_LIMIT, AVAILABILITY_FAILURE_LIMIT_MIN
    )
    connection_method: str | None = entry.data.get(CONF_CONNECTION_METHOD)
    return Device(
        hass,
        entry,
        name,
        device,
        port,
        device_id,
        operator_id,
        airco_id,
        availability_failure_limit=availability_failure_limit,
        connection_method=connection_method,
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: MitsubishiWfRacConfigEntry
) -> bool:
    """Handle unload of entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Only tear the coordinator down once the entities are really gone: if
    # unloading the platforms failed they stay loaded, and stopping their
    # coordinator would leave a loaded entry that never updates again.
    # An entry whose setup never got as far as storing its runtime data can
    # still be unloaded - there is simply no coordinator to shut down then.
    if unload_ok and (data := getattr(entry, "runtime_data", None)) is not None:
        await data.device.async_shutdown()

    if unload_ok:
        _LOGGER.info("Unloaded entry for device [%s]", entry.title)
    else:
        _LOGGER.warning("Failed to unload entry for device [%s]", entry.title)

    return unload_ok


async def async_remove_entry(
    hass: HomeAssistant, entry: MitsubishiWfRacConfigEntry
) -> None:
    """Handle removal of an entry."""

    temp_device = await create_device_from_entry(entry, hass)
    # delete_account() catches its own errors and returns None on failure (see
    # coordinator.py) rather than raising, so check the result instead of
    # try/except - the previous try/except here could never actually trigger,
    # and the "Deleted" log below used to fire unconditionally even on failure.
    result = await temp_device.delete_account()
    if result is not None:
        _LOGGER.info("Released the controller slot on airco [%s]", temp_device.airco_id)
    else:
        _LOGGER.warning(
            "Could not release the controller slot on airco [%s]. Free it in "
            "the manufacturer's app if you want it back",
            temp_device.airco_id,
        )

    # Entry-scoped, so it would otherwise dangle in the repair list forever
    # pointing at an entry_id that no longer resolves to anything.
    ir.async_delete_issue(hass, DOMAIN, registration_full_issue_id(entry.entry_id))
