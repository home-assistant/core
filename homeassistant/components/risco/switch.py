"""Support for bypassing Risco alarm zones."""

from typing import Any, override

from pyrisco.common import Zone

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import RiscoCloudZoneEntity, RiscoLocalZoneEntity
from .models import CloudData, RiscoConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RiscoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Risco switch."""
    risco_data = config_entry.runtime_data
    if local_data := risco_data.local_data:
        async_add_entities(
            RiscoLocalSwitch(local_data.system.id, zone_id, zone)
            for zone_id, zone in local_data.system.zones.items()
        )
    elif cloud_data := risco_data.cloud_data:
        async_add_entities(
            RiscoCloudSwitch(cloud_data, config_entry.entry_id, zone_id, zone)
            for zone_id, zone in cloud_data.alarm.zones.items()
        )


class RiscoCloudSwitch(RiscoCloudZoneEntity, SwitchEntity):
    """Representation of a bypass switch for a Risco cloud zone."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "bypassed"

    def __init__(
        self, cloud_data: CloudData, entry_id: str, zone_id: int, zone: Zone
    ) -> None:
        """Init the zone."""
        super().__init__(
            cloud_data=cloud_data,
            entry_id=entry_id,
            suffix="_bypassed",
            zone_id=zone_id,
            zone=zone,
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the zone is bypassed."""
        return self._zone.bypassed

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._bypass(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._bypass(False)

    async def _bypass(self, bypass: bool) -> None:
        alarm = await self._risco.bypass_zone(self._zone_id, bypass)
        self._cloud_data.alarm = alarm
        self._zone = alarm.zones[self._zone_id]
        self.async_write_ha_state()


class RiscoLocalSwitch(RiscoLocalZoneEntity, SwitchEntity):
    """Representation of a bypass switch for a Risco local zone."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "bypassed"

    def __init__(self, system_id: str, zone_id: int, zone: Zone) -> None:
        """Init the zone."""
        super().__init__(
            system_id=system_id,
            suffix="_bypassed",
            zone_id=zone_id,
            zone=zone,
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the zone is bypassed."""
        return self._zone.bypassed

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._bypass(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._bypass(False)

    async def _bypass(self, bypass: bool) -> None:
        await self._zone.bypass(bypass)
