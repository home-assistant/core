"""Platform for NASweb alarms."""

from __future__ import annotations

import logging
import time

from webio_api import Zone as NASwebZone
from webio_api.const import STATE_ZONE_ALARM, STATE_ZONE_ARMED, STATE_ZONE_DISARMED

from homeassistant.components.alarm_control_panel import (
    DOMAIN as DOMAIN_ALARM_CONTROL_PANEL,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    BaseCoordinatorEntity,
    BaseDataUpdateCoordinatorProtocol,
)

from . import NASwebConfigEntry
from .const import DOMAIN, STATUS_UPDATE_MAX_TIME_INTERVAL

_LOGGER = logging.getLogger(__name__)
ALARM_CONTROL_PANEL_TRANSLATION_KEY = "zone"

NASWEB_STATE_TO_HA_STATE = {
    STATE_ZONE_ALARM: AlarmControlPanelState.TRIGGERED,
    STATE_ZONE_ARMED: AlarmControlPanelState.ARMED_AWAY,
    STATE_ZONE_DISARMED: AlarmControlPanelState.DISARMED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config: NASwebConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up alarm control panel platform."""
    coordinator = config.runtime_data
    current_zones: set[int] = set()

    @callback
    def _check_entities() -> None:
        received_zones: dict[int, NASwebZone] = {
            entry.index: entry for entry in coordinator.webio_api.zones
        }
        added = {i for i in received_zones if i not in current_zones}
        removed = {i for i in current_zones if i not in received_zones}
        entities_to_add: list[ZoneEntity] = []
        for index in added:
            webio_zone = received_zones[index]
            if not isinstance(webio_zone, NASwebZone):
                _LOGGER.error("Cannot create ZoneEntity without NASwebZone")
                continue
            new_zone = ZoneEntity(coordinator, webio_zone)
            entities_to_add.append(new_zone)
            current_zones.add(index)
        async_add_entities(entities_to_add)
        entity_registry = er.async_get(hass)
        for index in removed:
            unique_id = f"{DOMAIN}.{config.unique_id}.zone.{index}"
            if entity_id := entity_registry.async_get_entity_id(
                DOMAIN_ALARM_CONTROL_PANEL, DOMAIN, unique_id
            ):
                entity_registry.async_remove(entity_id)
                current_zones.remove(index)
            else:
                _LOGGER.warning("Failed to remove old zone: no entity_id")

    coordinator.async_add_listener(_check_entities)
    _check_entities()


class ZoneEntity(AlarmControlPanelEntity, BaseCoordinatorEntity):
    """Entity representing NASweb zone."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = ALARM_CONTROL_PANEL_TRANSLATION_KEY

    def __init__(
        self, coordinator: BaseDataUpdateCoordinatorProtocol, nasweb_zone: NASwebZone
    ) -> None:
        """Initialize zone entity."""
        super().__init__(coordinator)
        self._zone = nasweb_zone
        self._attr_name = nasweb_zone.name
        self._attr_translation_placeholders = {"index": f"{nasweb_zone.index:2d}"}
        self._attr_unique_id = (
            f"{DOMAIN}.{self._zone.webio_serial}.zone.{self._zone.index}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._zone.webio_serial)},
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    def _set_attr_available(
        self, entity_last_update: float, available: bool | None
    ) -> None:
        if (
            self.coordinator.last_update is None
            or time.time() - entity_last_update >= STATUS_UPDATE_MAX_TIME_INTERVAL
        ):
            self._attr_available = False
        else:
            self._attr_available = available if available is not None else False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_alarm_state = NASWEB_STATE_TO_HA_STATE[self._zone.state]
        if self._zone.pass_type == 0:
            self._attr_code_format = CodeFormat.TEXT
        elif self._zone.pass_type == 1:
            self._attr_code_format = CodeFormat.NUMBER
        else:
            self._attr_code_format = None
        self._attr_code_arm_required = self._attr_code_format is not None

        self._set_attr_available(self._zone.last_update, self._zone.available)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        Scheduling updates is not necessary, the coordinator takes care of updates via push notifications.
        """

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        """Return the list of supported features."""
        return AlarmControlPanelEntityFeature.ARM_AWAY

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm away ZoneEntity."""
        await self._zone.arm(code)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm ZoneEntity."""
        await self._zone.disarm(code)
