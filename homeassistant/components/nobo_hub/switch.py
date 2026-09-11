"""Python Control of Nobø Hub - Nobø Energy Control."""

from typing import Any, override

from pynobo import PynoboError, nobo

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import ATTR_NAME, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NoboHubConfigEntry
from .const import ATTR_OVERRIDE_ALLOWED, DOMAIN
from .entity import NoboBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NoboHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the disable-global-override switches for the Nobø Ecohub."""
    hub = config_entry.runtime_data

    known_zones: set[str] = set()

    @callback
    def _add_switches(_hub: nobo) -> None:
        """Add disable-global-override switches for zones added to the hub."""
        if hub.connected:
            # Forget zones no longer on the hub so a removed-then-re-added zone
            # (the hub reuses zone ids) is detected as new again. Skip while
            # disconnected: a stale/empty snapshot would drop live zones and
            # cause duplicate re-adds on reconnect.
            known_zones.intersection_update(hub.zones)
        new_zones = [zone_id for zone_id in hub.zones if zone_id not in known_zones]
        known_zones.update(new_zones)
        async_add_entities(
            NoboDisableGlobalOverrideSwitch(hass, zone_id, hub, config_entry.entry_id)
            for zone_id in new_zones
        )

    _add_switches(hub)
    hub.register_callback(_add_switches)
    config_entry.async_on_unload(lambda: hub.deregister_callback(_add_switches))


class NoboDisableGlobalOverrideSwitch(NoboBaseEntity, SwitchEntity):
    """Controls whether a zone is excluded from the hub's global override.

    When on the zone keeps its week profile regardless of any global override
    set on the hub; when off the zone reacts to global overrides. Mirrors the
    "Disable global overrides" setting in the Nobø app.
    """

    _attr_translation_key = "disable_global_override"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, hass: HomeAssistant, zone_id: str, hub: nobo, entry_id: str
    ) -> None:
        """Initialize the disable-global-override switch."""
        super().__init__(hass, hub, entry_id)
        self._id = zone_id
        self._attr_unique_id = f"{hub.hub_serial}:{zone_id}:disable_global_override"
        zone_name = hub.zones[zone_id][ATTR_NAME]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{hub.hub_serial}:{zone_id}")},
            name=zone_name,
            via_device_id=self._hub_device_id,
            suggested_area=zone_name,
        )
        self._read_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Exclude this zone from global overrides."""
        await self._set_override_allowed(nobo.API.OVERRIDE_NOT_ALLOWED)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Allow global overrides to affect this zone."""
        await self._set_override_allowed(nobo.API.OVERRIDE_ALLOWED)

    async def _set_override_allowed(self, override_allowed: str) -> None:
        try:
            await self._nobo.async_update_zone(
                self._id, override_allowed=override_allowed
            )
        except PynoboError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_disable_global_override_failed",
            ) from err

    @property
    @override
    def available(self) -> bool:
        """Available when the hub is connected and the zone still exists."""
        return super().available and self._id in self._nobo.zones

    @callback
    @override
    def _read_state(self) -> None:
        """Read the current state from the hub. This is a local call."""
        if not self.available:
            return
        self._attr_is_on = (
            self._nobo.zones[self._id][ATTR_OVERRIDE_ALLOWED]
            == nobo.API.OVERRIDE_NOT_ALLOWED
        )
