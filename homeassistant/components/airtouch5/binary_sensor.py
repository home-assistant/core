"""Additional sensors for AirTouch 5 Devices."""
from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient
from airtouch5py.packets.ac_ability import AcAbility
from airtouch5py.packets.ac_status import AcStatus
from airtouch5py.packets.zone_name import ZoneName
from airtouch5py.packets.zone_status import ZoneStatusZone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import Airtouch5Entity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airtouch 5 Binary Sensor entities."""
    client: Airtouch5SimpleClient = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BinarySensorEntity] = []

    # Each AC has bypass, spill
    for ac in client.ac:
        entities.append(Airtouch5AcBypass(client, ac))
        entities.append(Airtouch5AcSpill(client, ac))

    # Each zone has a low battery sensor and spill flag
    for zone in client.zones:
        entities.append(Airtouch5ZoneLowBattery(client, zone))
        entities.append(Airtouch5ZoneSpill(client, zone))

    async_add_entities(entities)


class Airtouch5AcBypass(BinarySensorEntity, Airtouch5Entity):
    """Whether Bypass is active on a given AC device."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_name = "Bypass"

    def __init__(self, client: Airtouch5SimpleClient, ability: AcAbility) -> None:
        """Initialise the Binary Sensor."""
        super().__init__(client)
        self._ability = ability

        self._attr_unique_id = f"ac_{ability.ac_number}_bypass"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"ac_{ability.ac_number}")},
            name=f"AC {ability.ac_number} {ability.ac_name}",
            manufacturer="Polyaire",
            model="AirTouch 5",
        )

    @callback
    def _async_update_attrs(self, data: dict[int, AcStatus]) -> None:
        if self._ability.ac_number not in data:
            return
        status = data[self._ability.ac_number]

        self._attr_is_on = status.bypass_active

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add data updated listener after this object has been initialized."""
        await super().async_added_to_hass()
        self._client.ac_status_callbacks.append(self._async_update_attrs)
        self._async_update_attrs(self._client.latest_ac_status)

    async def async_will_remove_from_hass(self) -> None:
        """Remove data updated listener after this object has been initialized."""
        await super().async_will_remove_from_hass()
        self._client.ac_status_callbacks.remove(self._async_update_attrs)


class Airtouch5AcSpill(BinarySensorEntity, Airtouch5Entity):
    """Whether Spill is active on a given AC device."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_name = "Spill"

    def __init__(self, client: Airtouch5SimpleClient, ability: AcAbility) -> None:
        """Initialise the Binary Sensor."""
        super().__init__(client)
        self._ability = ability

        self._attr_unique_id = f"ac_{ability.ac_number}_spill"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"ac_{ability.ac_number}")},
            name=f"AC {ability.ac_number} {ability.ac_name}",
            manufacturer="Polyaire",
            model="AirTouch 5",
        )

    @callback
    def _async_update_attrs(self, data: dict[int, AcStatus]) -> None:
        if self._ability.ac_number not in data:
            return
        status = data[self._ability.ac_number]

        self._attr_is_on = status.spill_active

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add data updated listener after this object has been initialized."""
        await super().async_added_to_hass()
        self._client.ac_status_callbacks.append(self._async_update_attrs)
        self._async_update_attrs(self._client.latest_ac_status)

    async def async_will_remove_from_hass(self) -> None:
        """Remove data updated listener after this object has been initialized."""
        await super().async_will_remove_from_hass()
        self._client.ac_status_callbacks.remove(self._async_update_attrs)


class Airtouch5ZoneSpill(BinarySensorEntity, Airtouch5Entity):
    """Whether Spill is active in a given Zone."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_name = "Spill"

    def __init__(self, client: Airtouch5SimpleClient, name: ZoneName) -> None:
        """Initialise the Binary Sensor."""
        super().__init__(client)
        self._name = name

        self._attr_unique_id = f"zone_{name.zone_number}_spill"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"zone_{name.zone_number}")},
            name=name.zone_name,
            manufacturer="Polyaire",
            model="AirTouch 5",
        )

    @callback
    def _async_update_attrs(self, data: dict[int, ZoneStatusZone]) -> None:
        if self._name.zone_number not in data:
            return
        status = data[self._name.zone_number]

        self._attr_is_on = status.spill_active

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add data updated listener after this object has been initialized."""
        await super().async_added_to_hass()
        self._client.zone_status_callbacks.append(self._async_update_attrs)
        self._async_update_attrs(self._client.latest_zone_status)

    async def async_will_remove_from_hass(self) -> None:
        """Remove data updated listener after this object has been initialized."""
        await super().async_will_remove_from_hass()
        self._client.zone_status_callbacks.remove(self._async_update_attrs)


class Airtouch5ZoneLowBattery(BinarySensorEntity, Airtouch5Entity):
    """Whether the sensor battery is low in a given Zone."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_name = "Battery"

    def __init__(self, client: Airtouch5SimpleClient, name: ZoneName) -> None:
        """Initialise the Binary Sensor."""
        super().__init__(client)
        self._name = name

        self._attr_unique_id = f"zone_{name.zone_number}_low_battery"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"zone_{name.zone_number}")},
            name=name.zone_name,
            manufacturer="Polyaire",
            model="AirTouch 5",
        )

    @callback
    def _async_update_attrs(self, data: dict[int, ZoneStatusZone]) -> None:
        if self._name.zone_number not in data:
            return
        status = data[self._name.zone_number]

        self._attr_is_on = status.is_low_battery

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add data updated listener after this object has been initialized."""
        await super().async_added_to_hass()
        self._client.zone_status_callbacks.append(self._async_update_attrs)
        self._async_update_attrs(self._client.latest_zone_status)

    async def async_will_remove_from_hass(self) -> None:
        """Remove data updated listener after this object has been initialized."""
        await super().async_will_remove_from_hass()
        self._client.zone_status_callbacks.remove(self._async_update_attrs)
