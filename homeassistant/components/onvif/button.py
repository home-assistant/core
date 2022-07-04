"""ONVIF Buttons."""
from datetime import datetime, timezone
import time

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import ONVIFBaseEntity
from .const import DOMAIN
from .device import ONVIFDevice


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ONVIF button based on a config entry."""
    device = hass.data[DOMAIN][config_entry.unique_id]
    async_add_entities([RebootButton(device), SetSystemDateAndTimeButton(device)])


class RebootButton(ONVIFBaseEntity, ButtonEntity):
    """Defines a ONVIF reboot button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: ONVIFDevice) -> None:
        """Initialize the button entity."""
        super().__init__(device)
        self._attr_name = f"{self.device.name} Reboot"
        self._attr_unique_id = (
            f"{self.device.info.mac or self.device.info.serial_number}_reboot"
        )

    async def async_press(self) -> None:
        """Send out a SystemReboot command."""
        device_mgmt = self.device.device.create_devicemgmt_service()
        await device_mgmt.SystemReboot()


class SetSystemDateAndTimeButton(ONVIFBaseEntity, ButtonEntity):
    """Defines a ONVIF SetSystemDateAndTime button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: ONVIFDevice) -> None:
        """Initialize the button entity."""
        super().__init__(device)
        self._attr_name = f"{self.device.name} Set System Date and Time"
        self._attr_unique_id = f"{self.device.info.mac or self.device.info.serial_number}_setsystemdatetime"

    async def async_press(self) -> None:
        """Send out a SetSystemDateAndTime command."""
        device_mgmt = self.device.device.create_devicemgmt_service()
        now_utc = datetime.now(timezone.utc)
        current = await device_mgmt.GetSystemDateAndTime()

        dt_param = device_mgmt.create_type("SetSystemDateAndTime")
        dt_param.DateTimeType = "Manual"
        dt_param.DaylightSavings = bool(time.localtime().tm_isdst)
        dt_param.TimeZone = str(now_utc.astimezone().tzinfo)
        dt_param.UTCDateTime = current.UTCDateTime
        dt_param.UTCDateTime.Date.Year = now_utc.year
        dt_param.UTCDateTime.Date.Month = now_utc.month
        dt_param.UTCDateTime.Date.Day = now_utc.day
        dt_param.UTCDateTime.Time.Hour = now_utc.hour
        dt_param.UTCDateTime.Time.Minute = now_utc.minute
        dt_param.UTCDateTime.Time.Second = now_utc.second
        await device_mgmt.SetSystemDateAndTime(dt_param)
