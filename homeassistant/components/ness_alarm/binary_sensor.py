"""Support for Ness zone binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SIGNAL_ZONE_CHANGED
from .const import DEFAULT_MAX_SUPPORTED_ZONES, DOMAIN, PANEL_MODEL_ZONES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ness zone binary sensors from a config entry."""

    entity_registry = er.async_get(hass)

    panel_model = config_entry.data.get("panel_model", "UNKNOWN")

    if panel_model.startswith("MANUAL_"):
        try:
            zone_str = panel_model.split("_")[1]
            enabled_zones = int(zone_str)
        except (IndexError, ValueError):
            _LOGGER.warning(
                "Invalid manual model format '%s', defaulting to %s zones",
                panel_model,
                DEFAULT_MAX_SUPPORTED_ZONES,
            )
    elif panel_model in PANEL_MODEL_ZONES:
        enabled_zones = PANEL_MODEL_ZONES[panel_model]
    else:
        enabled_zones = DEFAULT_MAX_SUPPORTED_ZONES
        _LOGGER.warning(
            "Unknown panel model '%s', defaulting to %s zones",
            panel_model,
            enabled_zones,
        )

    entities = []

    async_add_entities(
        NessZoneBinarySensor(
            zone_id=zone_config[CONF_ZONE_ID],
            name=zone_config[CONF_ZONE_NAME],
            zone_type=zone_config[CONF_ZONE_TYPE],
        )
        for zone_config in configured_zones
    )

    async_add_entities(entities)


class NessZoneSensor(BinarySensorEntity):
    """Representation of a Ness zone sensor."""

    _attr_should_poll = False

    def __init__(
        self, zone_id: int, name: str, zone_type: BinarySensorDeviceClass
    ) -> None:
        """Initialize the binary_sensor."""
        self._zone_id = zone_id
        self._attr_name = name
        self._attr_device_class = zone_type
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Register callbacks and restore state."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ZONE_CHANGED,
                self._handle_zone_change,
            )
        )

    @callback
    def _handle_zone_change(self, data: ZoneChangedData) -> None:
        """Handle zone state update."""
        if self._zone_id == data.zone_id:
            self._attr_is_on = data.state
            self.async_write_ha_state()
