"""Python Control of Nobø Hub - Nobø Energy Control."""

from typing import override

from pynobo import PynoboError, nobo

from homeassistant.components.select import SelectEntity
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NoboHubConfigEntry
from .const import (
    ATTR_HARDWARE_VERSION,
    ATTR_SERIAL,
    ATTR_SOFTWARE_VERSION,
    CONF_OVERRIDE_TYPE,
    DOMAIN,
    NOBO_MANUFACTURER,
    OVERRIDE_TYPE_NOW,
)
from .entity import NoboBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NoboHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up any temperature sensors connected to the Nobø Ecohub."""
    hub = config_entry.runtime_data

    override_type = (
        nobo.API.OVERRIDE_TYPE_NOW
        if config_entry.options.get(CONF_OVERRIDE_TYPE) == OVERRIDE_TYPE_NOW
        else nobo.API.OVERRIDE_TYPE_CONSTANT
    )

    async_add_entities([NoboGlobalSelector(hub, override_type)], True)

    known_zones: set[str] = set()

    @callback
    def _add_profiles(_hub: nobo) -> None:
        """Add week-profile selectors for zones added to the hub."""
        if hub.connected:
            # Forget zones no longer on the hub so a removed-then-re-added zone
            # (the hub reuses zone ids) is detected as new again. Skip while
            # disconnected: a stale/empty snapshot would drop live zones and
            # cause duplicate re-adds on reconnect.
            known_zones.intersection_update(hub.zones)
        new_zones = [zone_id for zone_id in hub.zones if zone_id not in known_zones]
        known_zones.update(new_zones)
        async_add_entities(
            (NoboProfileSelector(zone_id, hub) for zone_id in new_zones), True
        )

    _add_profiles(hub)
    hub.register_callback(_add_profiles)
    config_entry.async_on_unload(lambda: hub.deregister_callback(_add_profiles))


class NoboGlobalSelector(NoboBaseEntity, SelectEntity):
    """Global override selector for Nobø Ecohub."""

    _attr_translation_key = "global_override"
    _modes = {
        nobo.API.OVERRIDE_MODE_NORMAL: "none",
        nobo.API.OVERRIDE_MODE_AWAY: "away",
        nobo.API.OVERRIDE_MODE_COMFORT: "comfort",
        nobo.API.OVERRIDE_MODE_ECO: "eco",
    }
    _attr_options = list(_modes.values())
    _attr_current_option: str | None = None

    def __init__(self, hub: nobo, override_type) -> None:
        """Initialize the global override selector."""
        super().__init__(hub)
        self._attr_unique_id = hub.hub_serial
        self._override_type = override_type
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub.hub_serial)},
            serial_number=hub.hub_serial,
            name=hub.hub_info[ATTR_NAME],
            manufacturer=NOBO_MANUFACTURER,
            model="Nobø Ecohub",
            sw_version=hub.hub_info[ATTR_SOFTWARE_VERSION],
            hw_version=hub.hub_info[ATTR_HARDWARE_VERSION],
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Set override."""
        mode = [k for k, v in self._modes.items() if v == option][0]
        try:
            await self._nobo.async_create_override(
                mode, self._override_type, nobo.API.OVERRIDE_TARGET_GLOBAL
            )
        except PynoboError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_global_override_failed",
            ) from err

    async def async_update(self) -> None:
        """Fetch new state data for this zone."""
        self._read_state()

    @callback
    @override
    def _read_state(self) -> None:
        """Copy the current hub state onto the entity attributes."""
        for override_data in self._nobo.overrides.values():
            if override_data["target_type"] == nobo.API.OVERRIDE_TARGET_GLOBAL:
                self._attr_current_option = self._modes[override_data["mode"]]
                break


class NoboProfileSelector(NoboBaseEntity, SelectEntity):
    """Week profile selector for Nobø zones."""

    _attr_translation_key = "week_profile"
    _attr_current_option: str | None = None

    def __init__(self, zone_id: str, hub: nobo) -> None:
        """Initialize the week profile selector."""
        super().__init__(hub)
        self._id = zone_id
        self._profiles: dict[str, str] = {}
        self._attr_options: list[str] = []
        self._attr_unique_id = f"{hub.hub_serial}:{zone_id}:profile"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{hub.hub_serial}:{zone_id}")},
            name=hub.zones[zone_id][ATTR_NAME],
            via_device=(DOMAIN, hub.hub_info[ATTR_SERIAL]),
            suggested_area=hub.zones[zone_id][ATTR_NAME],
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Set week profile."""
        week_profile_id = [k for k, v in self._profiles.items() if v == option][0]
        try:
            await self._nobo.async_update_zone(
                self._id, week_profile_id=week_profile_id
            )
        except PynoboError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_week_profile_failed",
            ) from err

    async def async_update(self) -> None:
        """Fetch new state data for this zone."""
        self._read_state()

    @property
    @override
    def available(self) -> bool:
        """Available when the hub is connected and the zone still exists."""
        return super().available and self._id in self._nobo.zones

    @callback
    @override
    def _read_state(self) -> None:
        """Read the current state from the hub. These are only local calls."""
        if not self.available:
            return
        self._profiles = {
            profile["week_profile_id"]: profile["name"].replace("\xa0", " ")
            for profile in self._nobo.week_profiles.values()
        }
        self._attr_options = sorted(self._profiles.values())
        self._attr_current_option = self._profiles[
            self._nobo.zones[self._id]["week_profile_id"]
        ]
