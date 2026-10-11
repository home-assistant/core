"""Support for fetching WiFi associations through SNMP."""

import binascii
from typing import override

import probatio

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    ScannerEntity,
)
from homeassistant.components.device_tracker.const import DEFAULT_CONSIDER_HOME
from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    AsyncSeeCallback,
    async_load_config,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST
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

from . import SnmpConfigEntry
from .const import (
    CONF_AUTH_KEY,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    DEFAULT_COMMUNITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE_TRACKER,
)
from .coordinator import SnmpDeviceTrackerCoordinator, normalize_mac

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_BASEOID): cv.string,
        probatio.Required(CONF_HOST): cv.string,
        probatio.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
        probatio.Inclusive(CONF_AUTH_KEY, "keys"): cv.string,
        probatio.Inclusive(CONF_PRIV_KEY, "keys"): cv.string,
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


async def _async_legacy_tracked_macs(hass: HomeAssistant) -> set[str]:
    """Return the MACs the legacy YAML configuration was tracking.

    The legacy integration registers no entities and adds the states of the
    devices it tracks only after this entry has been set up, so known_devices.yaml
    is the only record of which devices the user had enabled before the migration.
    """
    devices = await async_load_config(
        hass.config.path(YAML_DEVICES), hass, DEFAULT_CONSIDER_HOME
    )
    return {
        normalized
        for device in devices
        if device.track and (normalized := _legacy_tracked_mac(device.mac))
    }


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

    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    ):
        reason = result["reason"]
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

    # Only the devices the legacy YAML configuration was tracking are enabled, so an
    # upgrade does not disable the presence automations of the user. Anything else,
    # including a device seen for the first time after the migration, keeps the
    # disabled by default behaviour of the other router integrations.
    legacy_macs: set[str] = set()
    if entry.source == SOURCE_IMPORT:
        legacy_macs = await _async_legacy_tracked_macs(hass)

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER):
        _async_setup_subentry(
            entry, subentry.subentry_id, ent_reg, legacy_macs, async_add_entities
        )


@callback
def _async_setup_subentry(
    entry: SnmpConfigEntry,
    subentry_id: str,
    ent_reg: er.EntityRegistry,
    legacy_macs: set[str],
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
                SnmpTrackerEntity(coordinator, mac, was_tracked=mac in legacy_macs)
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
                SnmpTrackerEntity(coordinator, mac, was_tracked=mac in legacy_macs)
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
        was_tracked: bool = False,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_mac_address = mac
        self._attr_name = mac.replace(":", "_")
        self._attr_ip_address = coordinator.data.get(mac) if coordinator.data else None
        self._was_tracked = was_tracked

    @override
    async def async_added_to_hass(self) -> None:
        """Handle the entity being added to hass."""
        await super().async_added_to_hass()

        if not self._was_tracked:
            return

        # The migration keeps the entity id of the legacy tracker, so the user has
        # to be told when another entity claimed it in the meantime.
        mac = self._attr_mac_address
        entity_id = self.entity_id
        assert mac is not None
        assert entity_id is not None

        legacy_entity_id = f"{DEVICE_TRACKER_DOMAIN}.{mac.replace(':', '_')}"
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
        if self._was_tracked:
            return True
        return super().entity_registry_enabled_default
