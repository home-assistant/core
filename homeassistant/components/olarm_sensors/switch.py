"""Switches for Olar integration."""
import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta
import random
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_FIRMWARE,
    CONF_OLARM_DEVICES,
    DOMAIN,
    LOGGER,
    VERSION,
    BypassZone,
)
from .coordinator import OlarmCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add switches for Olarm alarm sensor zone bypassing."""

    # Defining the list to store the instances of each alarm zone bypass switch.
    entities = []
    pgm_entities = []

    for device in hass.data[DOMAIN]["devices"]:
        if device["deviceName"] not in entry.data[CONF_OLARM_DEVICES]:
            continue

        # Getting the instance of the DataCoordinator to update the data from Olarm.
        coordinator: OlarmCoordinator = hass.data[DOMAIN][device["deviceId"]]

        # Getting the first setup data from Olarm. eg: Panelstates, and all zones.

        LOGGER.info(
            "Setting up Olarm switches for device (%s)", coordinator.olarm_device_name
        )

        LOGGER.info(
            "Adding Olarm PGM switches for device (%s)", coordinator.olarm_device_name
        )
        # Looping through the pgm's for the panel.
        for sensor in coordinator.pgm_data:
            # Creating a sensor for each zone on the alarm panel.
            if sensor["pulse"]:
                continue

            pgm_switch = PGMSwitchEntity(
                coordinator=coordinator,
                name=sensor["name"],
                state=sensor["state"],
                enabled=sensor["enabled"],
                pgm_number=sensor["pgm_number"],
            )

            pgm_entities.append(pgm_switch)

        LOGGER.info(
            "Added Olarm PGM switches for device (%s)", coordinator.olarm_device_name
        )

        # Looping through the zones for the panel.
        LOGGER.info(
            "Adding Olarm Bypass switches for device (%s)",
            coordinator.olarm_device_name,
        )
        for sensordata in coordinator.bypass_state:
            # Creating a bypass button for each zone on the alarm panel.
            bypass_switch = BypassSwitchEntity(
                coordinator=coordinator,
                sensor_name=sensordata["name"],
                state=sensordata["state"],
                index=sensordata["zone_number"],
                last_changed=sensordata["last_changed"],
            )

            entities.append(bypass_switch)

        LOGGER.info(
            "Added Olarm Bypass switches for device (%s)", coordinator.olarm_device_name
        )

    # Adding Olarm Switches to Home Assistant
    async_add_entities(entities)
    async_add_entities(pgm_entities)
    LOGGER.info("Added Olarm PGM and Bypass switches for all devices")


class BypassSwitchEntity(SwitchEntity):
    """Representation of a switch for bypassing a zone."""

    def __init__(
        self,
        coordinator: OlarmCoordinator,
        sensor_name,
        state,
        index=None,
        last_changed=None,
    ) -> None:
        """Initialize the bypass switch entity."""
        self.coordinator = coordinator
        self.sensor_name = sensor_name
        self._state = state
        self.index = index
        self.last_changed = last_changed

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the zone bypass."""
        await asyncio.sleep(random.uniform(1.5, 3))
        await self.coordinator.api.bypass_zone(BypassZone(self.index + 1))
        await asyncio.sleep(random.uniform(1.5, 3))
        await self.coordinator.async_update_bypass_data()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the zone bypass."""
        await asyncio.sleep(random.uniform(1.5, 3))
        await self.coordinator.api.bypass_zone(BypassZone(self.index + 1))
        await asyncio.sleep(random.uniform(1.5, 3))
        await self.coordinator.async_update_bypass_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Write the state of the sensor to Home Assistant."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Handle the update of the new/updated data."""
        if datetime.now() - self.coordinator.last_update > timedelta(
            seconds=(1.5 * self.coordinator.entry.data[CONF_SCAN_INTERVAL])
        ):
            # Only update the state from the api if it has been more than 1.5 times the scan interval since the last update.
            await self.coordinator.async_update_bypass_data()

        self._state = self.coordinator.bypass_state[self.index]["state"]

    @property
    def available(self) -> bool:
        """Whether the entity is available. IE the coordinator updates successfully."""
        return (
            self.coordinator.last_update > datetime.now() - timedelta(minutes=2)
            and self.coordinator.device_online
        )

    @property
    def name(self) -> str:
        """The name of the zone from the Alarm Panel."""
        name = []
        name1 = self.sensor_name.replace("_", " ")
        for item in str(name1).lower().split(" "):
            if item == "bypass":
                continue

            name.append(str(item).capitalize())

        return " ".join(name) + " Bypass (" + self.coordinator.olarm_device_name + ")"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.coordinator.olarm_device_id}_bypass_switch_{self.index}"

    @property
    def should_poll(self) -> bool:
        """Disable polling. Integration will notify Home Assistant on sensor value update."""
        return False

    @property
    def icon(self) -> str:
        """Setting the icon of the entity depending on the state of the zone."""
        # Zone Bypass
        if self.is_on:
            return "mdi:shield-home-outline"

        return "mdi:shield-home"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.bypass_state[self.index]["state"] == "on"

    @property
    def device_state_attributes(self) -> Mapping[str, Any]:
        """The last time the state of the zone/ sensor changed on Olarm's side."""
        self.last_changed = self.coordinator.bypass_state[self.index]["last_changed"]
        return {"last_tripped_time": self.last_changed, "zone_number": self.index + 1}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            manufacturer="Raine Pretorius",
            name=f"Olarm Sensors ({self.coordinator.olarm_device_name})",
            model=self.coordinator.olarm_device_make,
            identifiers={(DOMAIN, self.coordinator.olarm_device_id)},
            sw_version=VERSION,
            hw_version=self.coordinator.entry.data[CONF_DEVICE_FIRMWARE],
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.bypass_state[self.index]["state"]
        self.async_write_ha_state()


class PGMSwitchEntity(SwitchEntity):
    """Representation of a custom switch entity."""

    def __init__(
        self,
        coordinator: OlarmCoordinator,
        name,
        state,
        enabled=True,
        pgm_number=None,
        pulse=False,
    ) -> None:
        """Initialize the custom switch entity."""
        self.coordinator = coordinator
        self.sensor_name = name
        self._state = state
        self.button_enabled = enabled
        self._pgm_number = pgm_number
        self.post_data: dict = {str: str | int}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the custom switch entity off."""
        self.post_data = {"actionCmd": "pgm-close", "actionNum": self._pgm_number}

        await self.coordinator.api.update_pgm(self.post_data)
        await self.coordinator.async_update_pgm_ukey_data()

        self._state = self.coordinator.pgm_data[self._pgm_number - 1]
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the custom switch entity off."""
        self.post_data = {"actionCmd": "pgm-open", "actionNum": self._pgm_number}

        await self.coordinator.api.update_pgm(self.post_data)
        await self.coordinator.async_update_pgm_ukey_data()

        self._state = self.coordinator.pgm_data[self._pgm_number - 1]
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when the entity is added to Home Assistant."""
        await super().async_added_to_hass()

    @property
    def available(self) -> bool:
        """Whether the entity is available. IE the coordinator updates successfully."""
        return (
            self.coordinator.last_update > datetime.now() - timedelta(minutes=2)
            and self.coordinator.device_online
        )

    @property
    def name(self) -> str:
        """Return the name of the custom switch entity."""
        return self.sensor_name + " (" + self.coordinator.olarm_device_name + ")"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.coordinator.olarm_device_id}_pgm_switch_{self._pgm_number}"

    @property
    def should_poll(self) -> bool:
        """Disable polling."""
        return False

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._state

    @property
    def icon(self) -> str:
        """Return the icon of the custom switch entity."""
        return "mdi:toggle-switch"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {
            "name": f"Olarm Sensors ({self.coordinator.olarm_device_name})",
            "manufacturer": "Raine Pretorius",
            "model": f"{self.coordinator.olarm_device_make}",
            "identifiers": {(DOMAIN, self.coordinator.olarm_device_id)},
            "sw_version": VERSION,
            "hw_version": f"{self.coordinator.device_firmware}",
        }
