"""Support for Drive sensors."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from .config_flow import configured_drivers
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=600)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an Drive sensor based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a drive sensor based on a rclone config entry."""
    from homeassistant.components.ais_drives_service import (
        rclone_get_remotes_long,
        DRIVES_TYPES,
    )

    remotes = rclone_get_remotes_long()
    conf_drives = configured_drivers(hass)
    sensors = []
    for remote in remotes:
        drive_type = remote["type"]
        try:
            code, icon = DRIVES_TYPES[drive_type]
        except Exception as e:
            icon = "mdi:nas"
        srn = slugify(remote["name"])
        sensors.append(DriveSensor(srn, icon, drive_type))

    async_add_entities(sensors, True)


class DriveSensor(Entity):
    """Implementation of a Drive sensor."""

    def __init__(self, name, icon, drive_type):
        """Initialize the Drive sensor."""
        self._icon = icon
        self._name = name
        self._attrs = {}
        self._drive_type = drive_type
        self._state = ""

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    # @property
    # def unit_of_measurement(self):
    #     """Return the unit of measurement of this entity, if any."""
    #     return '%'

    @property
    def device_info(self):
        return {
            "identifiers": {("Rclone", self._name)},
            "name": self._name,
            "manufacturer": "AI-Speaker",
            "model": self._drive_type,
            "sw_version": "Rclone",
            "via_device": None,
        }

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique, friendly identifier for this entity."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        pass

    async def async_update(self):
        """Get the latest data and update the state."""
        try:
            from homeassistant.components.ais_drives_service import G_RCLONE_CONF
            import subprocess

            self._state = ""
            rclone_cmd = ["rclone", "size", self._name + ":", G_RCLONE_CONF]
            proc = subprocess.run(
                rclone_cmd,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3,
            )
            #  will wait for the process to complete and then we are going to return the output
            if "" != proc.stderr:
                self._state = (
                    "Nie można pobrać informacji o pojemności dysku " + self._name
                )
                _LOGGER.error(str(proc.stderr))
            else:
                for li in proc.stdout.split("\n"):
                    self._state = self._state + li

        except Exception:
            pass
