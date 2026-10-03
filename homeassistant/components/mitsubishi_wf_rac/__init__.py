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
    """Bring an entry of the custom component that owns this domain up to date.

    Core never wrote versions 1 to 6; they come from that custom component,
    and an installation switching over brings its entries along. One
    normalisation brings any of them to the same shape: the host back into
    entry.data where setup reads it, the availability toggle and an unread
    retry key out, and the airco id as the unique id zeroconf matches on.
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

    # update() reports a failure in its return value rather than raising, so
    # an unreachable device gets HA's retry-with-backoff here.
    if not await _device.update():
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"device": device},
        )

    # Persisted so the next start skips protocol discovery. Nothing listens
    # for entry updates, so this does not reload the entry setting up.
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
    # Only entries carried over from the custom component name a limit;
    # nothing offers to set one here.
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

    # Only once the entities are really gone: platforms that failed to unload
    # stay loaded, and would be left with a coordinator that never updates.
    # An entry that never stored runtime data has none to shut down.
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
    # delete_account() returns None for everything short of a confirmed
    # release, which is what decides between the two lines.
    result = await temp_device.delete_account()
    if result is not None:
        _LOGGER.info("Released the controller slot on airco [%s]", temp_device.airco_id)
    else:
        _LOGGER.warning(
            "Could not release the controller slot on airco [%s]. Free it in "
            "the manufacturer's app if you want it back",
            temp_device.airco_id,
        )

    # Entry-scoped: it would otherwise dangle, pointing at a dead entry_id.
    ir.async_delete_issue(hass, DOMAIN, registration_full_issue_id(entry.entry_id))
