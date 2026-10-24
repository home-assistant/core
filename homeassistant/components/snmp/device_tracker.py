"""Support for fetching WiFi associations through SNMP."""

import binascii
from typing import override

import probatio

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.components.device_tracker.const import DEFAULT_CONSIDER_HOME
from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    async_load_config,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AUTH_KEY,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_CONTEXT_NAME,
    CONF_PRIV_KEY,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE_TRACKER,
)
from .coordinator import SnmpConfigEntry, SnmpDeviceTrackerCoordinator, normalize_mac

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_BASEOID): cv.string,
        probatio.Required(CONF_HOST): cv.string,
        probatio.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
        probatio.Inclusive(probatio.Secret(CONF_AUTH_KEY), "keys"): cv.string,
        probatio.Inclusive(probatio.Secret(CONF_PRIV_KEY), "keys"): cv.string,
    }
)


def _legacy_tracked_mac(mac: str | None) -> str | None:
    """Return the canonical MAC of a tracker from known_devices.yaml."""
    if not mac:
        return None
    try:
        # The legacy integration stored the value the device returned, so turn it
        # back into bytes and normalize it like the coordinator does.
        raw = binascii.unhexlify("".join(char for char in mac if char.isalnum()))
    except ValueError:
        return None
    return normalize_mac(raw)


async def _async_legacy_tracked_dev_ids(hass: HomeAssistant) -> dict[str, str]:
    """Return the entity ids of the trackers in known_devices.yaml, keyed by MAC.

    The legacy tracker keys its entities by a ``dev_id`` the user may have chosen,
    so the MAC alone is not enough to rebuild ``device_tracker.<dev_id>``. The
    legacy integration registers no entities and adds the states of the devices it
    tracks only after this entry has been set up, so known_devices.yaml is the only
    record of both the entity ids and which devices were enabled before migration.
    """
    devices = await async_load_config(
        hass.config.path(YAML_DEVICES), hass, DEFAULT_CONSIDER_HOME
    )
    return {
        normalized: device.dev_id
        for device in devices
        if device.track and (normalized := _legacy_tracked_mac(device.mac))
    }


@callback
def _is_migrated_table(hass: HomeAssistant, config: ConfigType) -> bool:
    """Return True if the table of this YAML block is already migrated."""
    baseoid = config[CONF_BASEOID]
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_HOST) != config[CONF_HOST]:
            continue
        if entry.data.get(CONF_PORT, DEFAULT_PORT) != config.get(
            CONF_PORT, DEFAULT_PORT
        ):
            continue
        # An import always targets the empty context, so a table polled through
        # another context did not migrate this block.
        if entry.data.get(CONF_CONTEXT_NAME):
            continue
        if any(
            subentry.data.get(CONF_BASEOID) == baseoid
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER)
        ):
            return True
    return False


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Trigger an import flow to migrate YAML config to a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )

    if result["type"] is FlowResultType.ABORT:
        reason = result["reason"]
        if reason != "already_configured":
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{reason}",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{reason}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "SNMP",
                    "host": config[CONF_HOST],
                },
            )
            return False

        baseoid = config[CONF_BASEOID]
        issue_id = (
            "deprecated_yaml_import_issue_multiple_trackers_"
            f"{config[CONF_HOST]}_{baseoid}"
        )
        if _is_migrated_table(hass, config):
            # Every block is imported again on a restart, so this one is covered
            ir.async_delete_issue(hass, DOMAIN, issue_id)
        else:
            # Another entry owns this agent, so this block was not migrated
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key="deprecated_yaml_import_issue_multiple_trackers",
                translation_placeholders={
                    "integration_title": "SNMP",
                    "host": config[CONF_HOST],
                    "baseoid": baseoid,
                },
            )
            return False

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "SNMP",
        },
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SnmpConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the device trackers of the entry's subentries."""
    ent_reg = er.async_get(hass)

    # On migration the legacy entity ids are reused, so an upgrade does not break
    # the automations of the user, and only the devices the legacy YAML
    # configuration was tracking are enabled. Anything else, including a device
    # seen for the first time after the migration, keeps the disabled by default
    # behaviour of the other router integrations.
    legacy_dev_ids: dict[str, str] = {}
    if entry.source == SOURCE_IMPORT:
        tracked_dev_ids = await _async_legacy_tracked_dev_ids(hass)
        # Once registered, the entity id belongs to the registry, so it is only
        # reused when the entity is allocated and never re-applied on a reload.
        legacy_dev_ids = {
            mac: dev_id
            for mac, dev_id in tracked_dev_ids.items()
            if ent_reg.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, mac) is None
        }

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER):
        _async_setup_subentry(
            entry, subentry.subentry_id, ent_reg, legacy_dev_ids, async_add_entities
        )


@callback
def _async_setup_subentry(
    entry: SnmpConfigEntry,
    subentry_id: str,
    ent_reg: er.EntityRegistry,
    legacy_dev_ids: dict[str, str],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the tracker entities of a single subentry."""
    coordinator = entry.runtime_data.coordinators[subentry_id]

    # Ensure previously known MACs show up as 'not_home' instead of disappearing
    # if missing from the current poll.
    initial_macs = {
        reg_entry.unique_id
        for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if reg_entry.unique_id
        and reg_entry.config_subentry_id == subentry_id
        and reg_entry.domain == DEVICE_TRACKER_DOMAIN
        and reg_entry.platform == DOMAIN
    }

    if initial_macs:
        async_add_entities(
            (
                SnmpTrackerEntity(
                    coordinator, mac, legacy_dev_id=legacy_dev_ids.get(mac)
                )
                for mac in initial_macs
            ),
            config_subentry_id=subentry_id,
        )

    tracked_macs = set(initial_macs)

    @callback
    def _handle_coordinator_update() -> None:
        """Handle updated data from the coordinator."""
        if not coordinator.data:
            return

        new_entities: list[SnmpTrackerEntity] = []
        for mac in coordinator.data:
            if mac in tracked_macs:
                continue
            tracked_macs.add(mac)
            new_entities.append(
                SnmpTrackerEntity(
                    coordinator, mac, legacy_dev_id=legacy_dev_ids.get(mac)
                )
            )

        if new_entities:
            async_add_entities(new_entities, config_subentry_id=subentry_id)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
    _handle_coordinator_update()


class SnmpTrackerEntity(CoordinatorEntity[SnmpDeviceTrackerCoordinator], ScannerEntity):
    """Represent an individual device tracked via SNMP."""

    def __init__(
        self,
        coordinator: SnmpDeviceTrackerCoordinator,
        mac: str,
        *,
        legacy_dev_id: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_mac_address = mac
        self._attr_name = mac
        self._attr_ip_address = coordinator.data.get(mac) if coordinator.data else None
        self._legacy_dev_id = legacy_dev_id
        if legacy_dev_id is not None:
            # Reuse the entity id the legacy YAML tracker used for this device, so
            # an upgrade keeps the automations referring to it working.
            self.entity_id = f"{DEVICE_TRACKER_DOMAIN}.{legacy_dev_id}"

    @override
    async def async_added_to_hass(self) -> None:
        """Handle the entity being added to hass."""
        await super().async_added_to_hass()

        if self._legacy_dev_id is None:
            return

        # The migration reuses the entity id of the legacy tracker, so the user
        # has to be told when another entity claimed it in the meantime.
        mac = self._attr_mac_address
        entity_id = self.entity_id
        assert mac is not None
        assert entity_id is not None

        legacy_entity_id = f"{DEVICE_TRACKER_DOMAIN}.{self._legacy_dev_id}"
        issue_id = f"entity_id_changed_{mac}"

        if entity_id == legacy_entity_id:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return

        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="entity_id_changed",
            translation_placeholders={
                "mac": mac,
                "entity_id": legacy_entity_id,
                "new_entity_id": entity_id,
            },
        )

    @property
    @override
    def is_connected(self) -> bool:
        """Return True if this MAC was seen in the latest scan."""
        if not self.coordinator.data:
            return False
        return self._attr_mac_address in self.coordinator.data

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attribute so base class can use it."""
        assert self._attr_mac_address is not None
        self._attr_ip_address = (
            self.coordinator.data.get(self._attr_mac_address)
            if self.coordinator.data
            else None
        )
        super()._handle_coordinator_update()

    @property
    @override
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity is enabled by default.

        A device that the legacy YAML configuration was tracking keeps the default
        Entity behaviour, so the migration does not silently disable the presence
        automations of the user. Any other device uses the ScannerEntity behaviour:
        enabled only when a device with the same MAC is already known.
        """
        if self._legacy_dev_id is not None:
            return True
        return super().entity_registry_enabled_default
