"""Support for Hydrawise cloud switches."""
from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from pydrawise import Controller, Zone
import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA,
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import (
    ALLOWED_WATERING_TIME,
    CONF_WATERING_TIME,
    DATA_YAML,
    DEFAULT_WATERING_TIME,
    DOMAIN,
    HydrawiseData,
    HydrawiseEntity,
)

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="auto_watering",
        name="Automatic Watering",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="manual_watering",
        name="Manual Watering",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)

SWITCH_KEYS: list[str] = [desc.key for desc in SWITCH_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SWITCH_KEYS): vol.All(
            cv.ensure_list, [vol.In(SWITCH_KEYS)]
        ),
        vol.Optional(CONF_WATERING_TIME, default=DEFAULT_WATERING_TIME): vol.All(
            vol.In(ALLOWED_WATERING_TIME)
        ),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hydrawise switches from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    data: HydrawiseData = coordinator.data
    entities: list[SwitchEntity] = []
    for ctrl_id in data.controllers.keys():
        entities.append(ControllerSwitch(coordinator, ctrl_id))
        for zone_id in data.zones[ctrl_id].keys():
            entities.append(ZoneSwitch(coordinator, ctrl_id, zone_id))
    async_add_entities(entities)


class ControllerSwitch(CoordinatorEntity, SwitchEntity):
    """Hydrawise Controller Switch entity."""

    _attr_icon = "mdi:water"

    def __init__(self, coordinator: DataUpdateCoordinator, ctrl_id: int) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.ctrl_id = ctrl_id
        self._attr_unique_id = str(self.ctrl_id)
        self._update_attrs()

    @property
    def _data(self) -> HydrawiseData:
        data: HydrawiseData = self.coordinator.data
        return data

    @property
    def _controller(self) -> Controller:
        return self._data.controllers[self.ctrl_id]

    @property
    def _zones(self) -> Iterable[Zone]:
        return self._data.zones[self.ctrl_id].values()

    def _update_attrs(self) -> None:
        self._attr_name = self._controller.name
        self._attr_is_on = all(
            z.scheduled_runs.current_run is not None for z in self._zones
        )
        self._attr_device_info = DeviceInfo(
            default_name=self._controller.name,
            manufacturer="Hunter",
            model=self._controller.hardware.model.description,
            sw_version=self._controller.software_version,
            identifiers={(DOMAIN, str(self.ctrl_id))},
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn all zones on."""
        await self._controller.start_all_zones()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn all zones off."""
        await self._controller.stop_all_zones()
        self._attr_is_on = False
        self.async_write_ha_state()


class ZoneSwitch(CoordinatorEntity, SwitchEntity):
    """Hydrawise Zone Switch entity."""

    _attr_icon = "mdi:water"

    def __init__(
        self, coordinator: DataUpdateCoordinator, ctrl_id: int, zone_id: int
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.ctrl_id = ctrl_id
        self.zone_id = zone_id
        self._attr_unique_id = str(self.zone_id)
        self._update_attrs()

    @property
    def _data(self) -> HydrawiseData:
        data: HydrawiseData = self.coordinator.data
        return data

    @property
    def _controller(self) -> Controller:
        return self._data.controllers[self.ctrl_id]

    @property
    def _zone(self) -> Zone:
        return self._data.zones[self.ctrl_id][self.zone_id]

    def _update_attrs(self) -> None:
        self._attr_name = self._zone.name
        self._attr_is_on = self._zone.scheduled_runs.current_run is not None
        self._attr_device_info = DeviceInfo(
            name=self._zone.name,
            model=self._zone.number.label,
            manufacturer="Hunter",
            identifiers={(DOMAIN, str(self.zone_id))},
            via_device=(DOMAIN, str(self.ctrl_id)),
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self._zone.start()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self._zone.stop()
        self._attr_is_on = False
        self.async_write_ha_state()


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for a Hydrawise device."""
    hydrawise = hass.data[DOMAIN][DATA_YAML].data
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    default_watering_timer = config[CONF_WATERING_TIME]

    entities = [
        HydrawiseSwitch(zone, description, default_watering_timer)
        for zone in hydrawise.relays
        for description in SWITCH_TYPES
        if description.key in monitored_conditions
    ]

    add_entities(entities, True)


class HydrawiseSwitch(HydrawiseEntity, SwitchEntity):
    """A switch implementation for Hydrawise device."""

    def __init__(
        self, data, description: SwitchEntityDescription, default_watering_timer
    ):
        """Initialize a switch for Hydrawise device."""
        super().__init__(data, description)
        self._default_watering_timer = default_watering_timer

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        relay_data = self.data["relay"] - 1
        if self.entity_description.key == "manual_watering":
            self.hass.data[DOMAIN][DATA_YAML].data.run_zone(
                self._default_watering_timer, relay_data
            )
        elif self.entity_description.key == "auto_watering":
            self.hass.data[DOMAIN][DATA_YAML].data.suspend_zone(0, relay_data)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        relay_data = self.data["relay"] - 1
        if self.entity_description.key == "manual_watering":
            self.hass.data[DOMAIN][DATA_YAML].data.run_zone(0, relay_data)
        elif self.entity_description.key == "auto_watering":
            self.hass.data[DOMAIN][DATA_YAML].data.suspend_zone(365, relay_data)

    def update(self) -> None:
        """Update device state."""
        relay_data = self.data["relay"] - 1
        mydata = self.hass.data[DOMAIN][DATA_YAML].data
        _LOGGER.debug("Updating Hydrawise switch: %s", self.name)
        if self.entity_description.key == "manual_watering":
            self._attr_is_on = mydata.relays[relay_data]["timestr"] == "Now"
        elif self.entity_description.key == "auto_watering":
            self._attr_is_on = (mydata.relays[relay_data]["timestr"] != "") and (
                mydata.relays[relay_data]["timestr"] != "Now"
            )
