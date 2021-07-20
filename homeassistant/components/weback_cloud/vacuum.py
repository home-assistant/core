"""Platform descriptor for Weback Cloud based Vacuum Robots."""
import datetime
import logging

import weback_unofficial.vacuum as wb_vacuum

from homeassistant.components.vacuum import (
    SUPPORT_BATTERY,
    SUPPORT_CLEAN_SPOT,
    SUPPORT_FAN_SPEED,
    SUPPORT_RETURN_HOME,
    SUPPORT_SEND_COMMAND,
    SUPPORT_STATUS,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    VacuumEntity,
)
from homeassistant.components.weback_cloud.const import DOMAIN
from homeassistant.components.weback_cloud.hub import WebackCloudHub
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEBACK = (
    SUPPORT_BATTERY
    | SUPPORT_RETURN_HOME
    | SUPPORT_CLEAN_SPOT
    | SUPPORT_STOP
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
    | SUPPORT_STATUS
    | SUPPORT_SEND_COMMAND
    | SUPPORT_FAN_SPEED
)

SCAN_INTERVAL = datetime.timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Weback Cloud devices using config entry."""
    hub: WebackCloudHub = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in hub.devices:
        entities.append(WebackVacuum(device=device))
    _LOGGER.debug("Adding Weback Vacuums to Home Assistant: %s", entities)
    async_add_entities(entities, True)


class WebackVacuum(VacuumEntity):
    """Weback Vacuums such as Neatsvor / Tesvor X500 and others."""

    def __init__(self, device: wb_vacuum.CleanRobot) -> None:
        """Initialize the Weback Vacuum."""
        self.device = device
        self.scan_interval = SCAN_INTERVAL
        self.last_fetch = None
        _LOGGER.debug("Vacuum has been initialized: %s", self.device.name)

    def update(self):
        """Update device's state."""
        self.device.update()

    def on_error(self, error):
        """Handle an error event from the robot."""
        self.hass.bus.fire(
            "weback_error", {"entity_id": self.entity_id, "error": error}
        )
        self.schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        if self.last_fetch is None:
            return True
        if (
            datetime.datetime.now() - self.last_fetch
        ).total_seconds() > self.scan_interval.total_seconds():
            return True
        return False

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return self.device.name

    @property
    def is_on(self):
        """Return true if vacuum is currently cleaning."""
        return self.device.is_cleaning

    @property
    def available(self):
        """Return true if vacuum is online."""
        return self.device.is_available

    @property
    def is_charging(self):
        """Return true if vacuum is currently charging."""
        return self.device.current_mode in wb_vacuum.CHARGING_STATES

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.nickname

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_WEBACK

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        return self.device.state

    def return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        self.device.return_home()

    @property
    def battery_icon(self):
        """Return the battery icon for the vacuum cleaner."""
        return icon_for_battery_level(
            battery_level=self.device.battery_level, charging=self.is_charging
        )

    @property
    def battery_charging(self):
        """Return true in when robot is charging."""
        return self.device.is_charging

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self.device.battery_level

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return self.device.shadow.get("fan_status")

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return [wb_vacuum.FAN_SPEED_NORMAL, wb_vacuum.FAN_SPEED_HIGH]

    @property
    def device_state_attributes(self):
        """Return the device-specific state attributes of this vacuum."""
        return {"raw_state": self.device.current_mode}

    def turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning."""
        self.device.turn_on()

    def turn_off(self, **kwargs):
        """Turn the vacuum off stopping the cleaning and returning home."""
        self.return_to_base()

    def stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        self.device.stop()

    def clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        self.device.publish_single("working_status", wb_vacuum.CLEAN_MODE_SPOT)

    def set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if self.is_on:
            self.device.publish_single("fan_status", fan_speed)

    def send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        self.device.publish(params)
