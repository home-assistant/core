"""Python Control of Nobø Hub - Nobø Energy Control."""
from __future__ import annotations

from pynobo import nobo

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_HARDWARE_VERSION,
    ATTR_SERIAL,
    ATTR_SOFTWARE_VERSION,
    CONF_OVERRIDE_TYPE,
    DOMAIN,
    NOBO_MANUFACTURER,
    OVERRIDE_TYPE_NOW,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up any temperature sensors connected to the Nobø Ecohub."""

    # Setup connection with hub
    hub: nobo = hass.data[DOMAIN][config_entry.entry_id]

    override_type = (
        nobo.API.OVERRIDE_TYPE_NOW
        if config_entry.options.get(CONF_OVERRIDE_TYPE) == OVERRIDE_TYPE_NOW
        else nobo.API.OVERRIDE_TYPE_CONSTANT
    )

    entities: list[SelectEntity] = [
        NoboProfileSelector(zone_id, hub) for zone_id in hub.zones
    ]
    entities.append(NoboGlobalSelector(hub, override_type))
    async_add_entities(entities, True)


class NoboGlobalSelector(SelectEntity):
    """Global override selector for Nobø Ecohub."""

    _attr_has_entity_name = True
    _attr_translation_key = "global_override"
    _attr_device_class = "nobo_hub__override"
    _attr_should_poll = False
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
        self._nobo = hub
        self._attr_unique_id = hub.hub_serial
        self._override_type = override_type
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub.hub_serial)},
            name=hub.hub_info[ATTR_NAME],
            manufacturer=NOBO_MANUFACTURER,
            model=f"Nobø Ecohub ({hub.hub_info[ATTR_HARDWARE_VERSION]})",
            sw_version=hub.hub_info[ATTR_SOFTWARE_VERSION],
        )

    async def async_added_to_hass(self) -> None:
        """Register callback from hub."""
        self._nobo.register_callback(self._after_update)

    async def async_will_remove_from_hass(self) -> None:
        """Deregister callback from hub."""
        self._nobo.deregister_callback(self._after_update)

    async def async_select_option(self, option: str) -> None:
        """Set override."""
        mode = [k for k, v in self._modes.items() if v == option][0]
        try:
            await self._nobo.async_create_override(
                mode, self._override_type, nobo.API.OVERRIDE_TARGET_GLOBAL
            )
        except Exception as exp:
            raise HomeAssistantError from exp

    async def async_update(self) -> None:
        """Fetch new state data for this zone."""
        self._read_state()

    @callback
    def _read_state(self) -> None:
        for override in self._nobo.overrides.values():
            if override["target_type"] == nobo.API.OVERRIDE_TARGET_GLOBAL:
                self._attr_current_option = self._modes[override["mode"]]
                break

    @callback
    def _after_update(self, hub) -> None:
        self._read_state()
        self.async_write_ha_state()


class NoboProfileSelector(SelectEntity):
    """Week profile selector for Nobø zones."""

    _attr_translation_key = "week_profile"
    _attr_has_entity_name = True
    _attr_should_poll = False
    _profiles: dict[int, str] = {}
    _attr_options: list[str] = []
    _attr_current_option: str | None = None

    def __init__(self, zone_id: str, hub: nobo) -> None:
        """Initialize the week profile selector."""
        self._id = zone_id
        self._nobo = hub
        self._attr_unique_id = f"{hub.hub_serial}:{zone_id}:profile"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{hub.hub_serial}:{zone_id}")},
            name=hub.zones[zone_id][ATTR_NAME],
            via_device=(DOMAIN, hub.hub_info[ATTR_SERIAL]),
            suggested_area=hub.zones[zone_id][ATTR_NAME],
        )

    async def async_added_to_hass(self) -> None:
        """Register callback from hub."""
        self._nobo.register_callback(self._after_update)

    async def async_will_remove_from_hass(self) -> None:
        """Deregister callback from hub."""
        self._nobo.deregister_callback(self._after_update)

    async def async_select_option(self, option: str) -> None:
        """Set week profile."""
        week_profile_id = [k for k, v in self._profiles.items() if v == option][0]
        try:
            await self._nobo.async_update_zone(
                self._id, week_profile_id=week_profile_id
            )
        except Exception as exp:
            raise HomeAssistantError from exp

    async def async_update(self) -> None:
        """Fetch new state data for this zone."""
        self._read_state()

    @callback
    def _read_state(self) -> None:
        self._profiles = {
            profile["week_profile_id"]: profile["name"].replace("\xa0", " ")
            for profile in self._nobo.week_profiles.values()
        }
        self._attr_options = sorted(self._profiles.values())
        self._attr_current_option = self._profiles[
            self._nobo.zones[self._id]["week_profile_id"]
        ]

    @callback
    def _after_update(self, hub) -> None:
        self._read_state()
        self.async_write_ha_state()
