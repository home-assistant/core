"""Support for Ecovacs Ecovacs Vacuums."""
from __future__ import annotations

import logging
from typing import Any

import sucks

from homeassistant.components.vacuum import VacuumEntity, VacuumEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import ECOVACS_DEVICES

_LOGGER = logging.getLogger(__name__)

ATTR_ERROR = "error"
ATTR_COMPONENT_PREFIX = "component_"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ecovacs vacuums."""
    vacuums = []
    for device in hass.data[ECOVACS_DEVICES]:
        vacuums.append(EcovacsVacuum(device))
    _LOGGER.debug("Adding Ecovacs Vacuums to Home Assistant: %s", vacuums)
    add_entities(vacuums, True)


class EcovacsVacuum(VacuumEntity):
    """Ecovacs Vacuums such as Deebot."""

    _attr_fan_speed_list = [sucks.FAN_SPEED_NORMAL, sucks.FAN_SPEED_HIGH]
    _attr_should_poll = False
    _attr_supported_features = (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.TURN_OFF
        | VacuumEntityFeature.TURN_ON
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.STATUS
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.FAN_SPEED
    )

    def __init__(self, device: sucks.VacBot) -> None:
        """Initialize the Ecovacs Vacuum."""
        self.device = device
        self.device.connect_and_wait_until_ready()
        if self.device.vacuum.get("nick") is not None:
            self._attr_name = str(self.device.vacuum["nick"])
        else:
            # In case there is no nickname defined, use the device id
            self._attr_name = str(format(self.device.vacuum["did"]))

        self._error = None
        _LOGGER.debug("Vacuum initialized: %s", self.name)

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        self.device.statusEvents.subscribe(lambda _: self.schedule_update_ha_state())
        self.device.batteryEvents.subscribe(lambda _: self.schedule_update_ha_state())
        self.device.lifespanEvents.subscribe(lambda _: self.schedule_update_ha_state())
        self.device.errorEvents.subscribe(self.on_error)

    def on_error(self, error):
        """Handle an error event from the robot.

        This will not change the entity's state. If the error caused the state
        to change, that will come through as a separate on_status event
        """
        if error == "no_error":
            self._error = None
        else:
            self._error = error

        self.hass.bus.fire(
            "ecovacs_error", {"entity_id": self.entity_id, "error": error}
        )
        self.schedule_update_ha_state()

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return self.device.vacuum.get("did")

    @property
    def is_on(self) -> bool:
        """Return true if vacuum is currently cleaning."""
        return self.device.is_cleaning

    @property
    def is_charging(self) -> bool:
        """Return true if vacuum is currently charging."""
        return self.device.is_charging

    @property
    def status(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return self.device.vacuum_status

    def return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""

        self.device.run(sucks.Charge())

    @property
    def battery_icon(self) -> str:
        """Return the battery icon for the vacuum cleaner."""
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=self.is_charging
        )

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        if self.device.battery_status is not None:
            return self.device.battery_status * 100

        return super().battery_level

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self.device.fan_speed

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the vacuum on and start cleaning."""

        self.device.run(sucks.Clean())

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the vacuum off stopping the cleaning and returning home."""
        self.return_to_base()

    def stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""

        self.device.run(sucks.Stop())

    def clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""

        self.device.run(sucks.Spot())

    def locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""

        self.device.run(sucks.PlaySound())

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        if self.is_on:
            self.device.run(sucks.Clean(mode=self.device.clean_status, speed=fan_speed))

    def send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        self.device.run(sucks.VacBotCommand(command, params))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device-specific state attributes of this vacuum."""
        data: dict[str, Any] = {}
        data[ATTR_ERROR] = self._error

        for key, val in self.device.components.items():
            attr_name = ATTR_COMPONENT_PREFIX + key
            data[attr_name] = int(val * 100)

        return data
