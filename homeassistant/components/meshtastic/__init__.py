"""The Meshtastic integration."""

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from . import repairs
from .client import MeshtasticClient, MeshtasticError
from .const import (
    CONF_DOWNLOAD_NODE_DB,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DEFAULT_DOWNLOAD_NODE_DB,
    DEFAULT_PORT,
    DOMAIN,
    LEGACY_CONF_TCP_HOST,
    LEGACY_CONF_TCP_PORT,
    LOGGER,
    MANUFACTURER,
    PLATFORMS,
    gateway_device_id,
    node_device_id,
)
from .coordinator import (
    MeshtasticConfigEntry,
    MeshtasticCoordinator,
    MeshtasticNodeRegistry,
    MeshtasticRuntimeData,
)
from .services import async_setup_services

#: Platform modules import the entry type from the package, which is where the
#: rest of Home Assistant expects to find it; it is defined in ``coordinator``.
__all__ = ["MeshtasticConfigEntry"]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Meshtastic integration.

    The actions are registered here rather than in ``async_setup_entry`` so
    that an automation that calls one still validates while no entry is loaded.
    """
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MeshtasticConfigEntry) -> bool:
    """Set up Meshtastic from a config entry."""
    client = MeshtasticClient(
        hass,
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        # The flag was part of the user step before it became an option, so an
        # entry created back then still carries it in its data.
        download_node_db=entry.options.get(
            CONF_DOWNLOAD_NODE_DB,
            entry.data.get(CONF_DOWNLOAD_NODE_DB, DEFAULT_DOWNLOAD_NODE_DB),
        ),
    )
    coordinator = MeshtasticCoordinator(hass, entry, client)
    await coordinator.async_load_stored_nodes()

    try:
        await client.async_start()
    except MeshtasticError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": client.host},
        ) from err

    entry.async_on_unload(client.async_stop)
    entry.runtime_data = MeshtasticRuntimeData(client=client, coordinator=coordinator)

    # Register the gateway device before forwarding platforms so node entities
    # can resolve it as their via_device parent whatever order they set up in.
    gateway = coordinator.gateway
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, gateway_device_id(gateway.node_num))},
        manufacturer=MANUFACTURER,
        model=gateway.hardware_model,
        name=gateway.name,
        sw_version=gateway.firmware_version,
        serial_number=gateway.node_id,
    )

    # Repair issues follow from live state, so they are reconciled on every
    # coordinator update: a link that keeps being kicked raises one, a node
    # that is heard again withdraws one.  The check is cheap and idempotent.
    @callback
    def _check_issues() -> None:
        repairs.async_check_issues(hass, entry)

    entry.async_on_unload(coordinator.async_add_listener(_check_issues))
    _check_issues()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeshtasticConfigEntry) -> bool:
    """Unload a Meshtastic config entry."""
    # The live issues describe a link that no longer exists once the entry is
    # unloaded; the migration issue is deliberately left standing.
    repairs.async_delete_issues(hass, entry)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: MeshtasticConfigEntry) -> None:
    """Delete the persisted node table when the entry is removed."""
    repairs.async_delete_issues(hass, entry)
    await MeshtasticNodeRegistry(hass, entry.entry_id).async_remove()


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: MeshtasticConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow removing a node device that the mesh no longer knows about.

    The gateway device itself always stays: removing it would mean removing the
    config entry.
    """
    coordinator = config_entry.runtime_data.coordinator
    if (gateway := coordinator.gateway_or_none) is None:
        return False
    known = {gateway_device_id(gateway.node_num)} | {
        node_device_id(gateway.node_num, node.num)
        for node in coordinator.nodes.values()
    }
    return not any(
        identifier[1] in known
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
    )


async def async_migrate_entry(
    hass: HomeAssistant, entry: MeshtasticConfigEntry
) -> bool:
    """Migrate an old config entry.

    This also picks up an entry left behind by the ``meshtastic`` custom
    integration from HACS, which stores the host under ``tcp_host`` /
    ``tcp_port``.  Without this the entry would survive removal of the custom
    component and then fail with a ``KeyError`` on every setup.
    """
    if entry.version > CONFIG_ENTRY_VERSION:
        return False

    data = dict(entry.data)
    if CONF_HOST not in data and LEGACY_CONF_TCP_HOST in data:
        LOGGER.debug("Migrating a config entry from the custom integration")
        data[CONF_HOST] = data.pop(LEGACY_CONF_TCP_HOST)
        data[CONF_PORT] = data.pop(LEGACY_CONF_TCP_PORT, DEFAULT_PORT)
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            version=CONFIG_ENTRY_VERSION,
            minor_version=CONFIG_ENTRY_MINOR_VERSION,
        )
        # The devices and entities are this integration's, not the custom
        # component's, and both would fight over the node's single client slot.
        repairs.async_create_migration_issue(hass, entry)
        return True

    if CONF_HOST not in data:
        # A serial or Bluetooth entry from the custom integration; this
        # integration only speaks TCP, so there is nothing to carry over.
        LOGGER.error(
            "Cannot migrate the Meshtastic config entry: it has no TCP host."
            " Remove it and add the integration again"
        )
        return False

    # Nothing to convert, but the entry is still on an older minor version;
    # record the new one or it would be migrated again on every start.
    hass.config_entries.async_update_entry(
        entry, minor_version=CONFIG_ENTRY_MINOR_VERSION
    )
    return True
