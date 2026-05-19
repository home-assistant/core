"""ONVIF Buttons."""

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import ONVIFConfigEntry, ONVIFDevice
from .entity import ONVIFBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ONVIFConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ONVIF button based on a config entry."""
    device = config_entry.runtime_data
    async_add_entities([RebootButton(device), SetSystemDateAndTimeButton(device)])


class RebootButton(ONVIFBaseEntity, ButtonEntity):
    """Defines a ONVIF reboot button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: ONVIFDevice) -> None:
        """Initialize the button entity."""
        super().__init__(device)
        self._attr_name = f"{self.device.name} Reboot"
        self._attr_unique_id = f"{self.mac_or_serial}_reboot"

    async def async_press(self) -> None:
        """Send out a SystemReboot command."""
        device_mgmt = await self.device.device.create_devicemgmt_service()
        await device_mgmt.SystemReboot()


class SetSystemDateAndTimeButton(ONVIFBaseEntity, ButtonEntity):
    """Defines a ONVIF SetSystemDateAndTime button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: ONVIFDevice) -> None:
        """Initialize the button entity."""
        super().__init__(device)
        self._attr_name = f"{self.device.name} Set System Date and Time"
        self._attr_unique_id = f"{self.mac_or_serial}_setsystemdatetime"

    async def async_press(self) -> None:
        """Send out a SetSystemDateAndTime command."""
        await self.device.async_manually_set_date_and_time()
