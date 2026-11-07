"""The Mitsubishi WF-RAC integration."""

import logging

from pywfrac import Repository, WfRacError

from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AIRCO_ID,
    CONF_AVAILABILITY_CHECK,
    CONF_AVAILABILITY_RETRY_LIMIT,
    CONF_CONNECTION_METHOD,
    CONF_OPERATOR_ID,
    DOMAIN,
)
from .coordinator import (
    MitsubishiWfRacConfigEntry,
    MitsubishiWfRacData,
    WfRacCoordinator,
    registration_full_issue_id,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE]


def _create_repository(
    hass: HomeAssistant, entry: MitsubishiWfRacConfigEntry
) -> Repository:
    """Build the library client for a config entry."""
    return Repository(
        async_get_clientsession(hass),
        # Entries below version 8 may still keep the host in options.
        entry.data.get(CONF_HOST) or entry.options[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_OPERATOR_ID],
        entry.data[CONF_DEVICE_ID],
        method=entry.data.get(CONF_CONNECTION_METHOD),
        time_zone=hass.config.time_zone,
    )


async def async_migrate_entry(
    hass: HomeAssistant, entry: MitsubishiWfRacConfigEntry
) -> bool:
    """Migrate entries of versions below 8 to the current shape."""
    if entry.version < 8:
        data = dict(entry.data)
        options = dict(entry.options)

        if CONF_HOST in options:
            data[CONF_HOST] = options.pop(CONF_HOST)

        options.pop(CONF_AVAILABILITY_CHECK, None)
        options.pop("availability_retry", None)
        options.pop(CONF_AVAILABILITY_RETRY_LIMIT, None)

        unique_id = data[CONF_AIRCO_ID].lower()
        other = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, unique_id)
        if other is not None and other.entry_id != entry.entry_id:
            _LOGGER.error(
                "Entries %s and %s belong to the same airco; delete one of them",
                entry.title,
                other.title,
            )
            return False

        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            unique_id=unique_id,
            version=8,
        )

    if entry.minor_version < 2:
        old_unique_id = f"{DOMAIN}-{entry.data[CONF_AIRCO_ID]}-climate"
        new_unique_id = entry.data[CONF_AIRCO_ID].lower()

        @callback
        def _migrate_unique_id(
            entity_entry: er.RegistryEntry,
        ) -> dict[str, str] | None:
            if entity_entry.unique_id != old_unique_id:
                return None
            return {"new_unique_id": new_unique_id}

        await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MitsubishiWfRacConfigEntry
) -> bool:
    """Establish connection with mitsubishi-wf-rac."""
    repository = _create_repository(hass, entry)
    coordinator = WfRacCoordinator(hass, entry, repository)
    await coordinator.async_config_entry_first_refresh()

    # Persisted so the next start skips protocol discovery.
    method = coordinator.connection_method
    if method and entry.data.get(CONF_CONNECTION_METHOD) != method:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_CONNECTION_METHOD: method}
        )
        _LOGGER.debug("Persisted connection method [%s] for [%s]", method, entry.title)

    entry.runtime_data = MitsubishiWfRacData(coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MitsubishiWfRacConfigEntry
) -> bool:
    """Handle unload of entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: MitsubishiWfRacConfigEntry
) -> None:
    """Handle removal of an entry."""
    # The issue is entry-scoped and would otherwise outlive the entry.
    ir.async_delete_issue(hass, DOMAIN, registration_full_issue_id(entry.entry_id))

    airco_id: str = entry.data[CONF_AIRCO_ID]
    # Operator and device ids are shared, so this would free the survivor's slot.
    if any(
        other.entry_id != entry.entry_id
        and other.data.get(CONF_AIRCO_ID, "").lower() == airco_id.lower()
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        _LOGGER.debug(
            "Keeping the controller slot on airco [%s]: still in use", airco_id
        )
        return

    repository = _create_repository(hass, entry)
    try:
        released = await repository.async_unregister(airco_id)
    except WfRacError:
        released = False
    if released:
        _LOGGER.info("Released the controller slot on airco [%s]", airco_id)
    else:
        _LOGGER.warning(
            "Could not release the controller slot on airco [%s]. Free it in "
            "the manufacturer's app if you want it back",
            airco_id,
        )
