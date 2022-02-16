"""ONVIF Buttons."""
from datetime import datetime

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG
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

    _attr_entity_category = ENTITY_CATEGORY_CONFIG

    def __init__(self, device: ONVIFDevice) -> None:
        """Initialize the button entity."""
        super().__init__(device)
        self._attr_name = f"{self.device.name} Set System Date and Time"
        self._attr_unique_id = f"{self.device.info.mac or self.device.info.serial_number}_setsystemdatetime"

    async def async_press(self) -> None:
        """Send out a SetSystemDateAndTime command."""
        device_mgmt = self.device.device.create_devicemgmt_service()
        now = datetime.now()
        current = await device_mgmt.GetSystemDateAndTime()

        dt_param = device_mgmt.create_type("SetSystemDateAndTime")
        dt_param.DateTimeType = "Manual"
        dt_param.DaylightSavings = current.DaylightSavings
        dt_param.TimeZone = current.TimeZone
        dt_param.UTCDateTime = current.UTCDateTime
        dt_param.UTCDateTime.Date.Year = now.year
        dt_param.UTCDateTime.Date.Month = now.month
        dt_param.UTCDateTime.Date.Day = now.day
        dt_param.UTCDateTime.Time.Hour = now.hour
        dt_param.UTCDateTime.Time.Minute = now.minute
        dt_param.UTCDateTime.Time.Second = now.second
        await device_mgmt.SetSystemDateAndTime(dt_param)
