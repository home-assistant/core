"""Base entity for Hikvision integration."""

from typing import override

from pyhik.image import ImageSetting

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import HikvisionConfigEntry
from .const import DOMAIN
from .coordinator import HikvisionImageCoordinator


class HikvisionEntity(Entity):
    """Base class for Hikvision entities."""

    _attr_has_entity_name = True

    # pyhik routes an update to the callbacks registered under this exact
    # identifier and passes it back as the callback message. It also
    # broadcasts to every registered callback when the event stream
    # connects or drops, which is what drives availability.
    _callback_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HikvisionConfigEntry,
        channel: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self._data = entry.runtime_data
        self._camera = self._data.camera
        self._channel = channel

        if self._data.device_type == "NVR":
            # NVR channels get their own device linked to the NVR via via_device_id
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{self._data.device_id}_{channel}")},
                via_device_id=dr.async_get_device_id_by_identifier(
                    hass, (DOMAIN, self._data.device_id), config_entry_id=entry.entry_id
                ),
                translation_key="nvr_channel",
                translation_placeholders={
                    "device_name": self._data.device_name,
                    "channel_number": str(channel),
                },
                manufacturer="Hikvision",
                model="NVR channel",
            )
        else:
            # Single camera device
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._data.device_id)},
                name=self._data.device_name,
                manufacturer="Hikvision",
                model=self._data.device_type,
            )

    @property
    @override
    def available(self) -> bool:
        """Return true if the device's event stream is connected."""
        return self._camera.stream_connected

    @override
    async def async_added_to_hass(self) -> None:
        """Register callback when entity is added, and drop it on removal."""
        await super().async_added_to_hass()

        self._camera.add_update_callback(self._update_callback, self._callback_id)
        self.async_on_remove(
            lambda: self._camera.remove_update_callback(
                self._update_callback, self._callback_id
            )
        )

    def _update_callback(self, msg: str) -> None:
        """Update the entity state when the callback is triggered.

        This is called from pyhik event stream thread, so we use
        schedule_update_ha_state which is thread-safe.
        """
        self.schedule_update_ha_state()


class HikvisionImageEntity(CoordinatorEntity[HikvisionImageCoordinator]):
    """Base class for the image setting entities of a camera."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HikvisionImageCoordinator,
        entry: HikvisionConfigEntry,
        description: EntityDescription,
        path: str,
    ) -> None:
        """Initialize the entity.

        The path is the camera's own spelling of the setting, used for requests.
        """
        super().__init__(coordinator)
        data = entry.runtime_data
        self.entity_description = description
        self._path = path
        # From the key of the description, not from the path: the firmware can spell
        # or shape a path differently, and the entity must stay the same.
        self._attr_unique_id = f"{data.device_id}_image_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data.device_id)},
            name=data.device_name,
            manufacturer="Hikvision",
            model=data.device_type,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the camera reports the setting now.

        Some settings only exist in one mode, like the levels of the advanced noise
        reduction: the camera leaves them out while another mode is used, and
        refuses to write them.
        """
        return super().available and self._reported

    @property
    def _reported(self) -> bool:
        """Return whether the current values of the camera have the setting."""
        return self._path in self.coordinator.data

    @property
    def _value(self) -> str | None:
        """Return the current raw value of the setting."""
        return self.coordinator.data.get(self._path)


def image_option_map(setting: ImageSetting, translate: bool) -> dict[str, str] | None:
    """Return the entity option for each value the camera accepts.

    Returns None if two camera values would end up with the same option, or only
    differ in case.
    """
    # Untranslated options are checked too: a camera can list the same value
    # twice, which pyHik keeps.
    options = {
        slugify(option) if translate else option: option for option in setting.options
    }
    if len(options) != len(setting.options):
        return None
    # The camera's value is read in any case: values that only differ in case
    # could not be told apart.
    if len({value.lower() for value in setting.options}) != len(setting.options):
        return None
    return options


class HikvisionImageChoiceEntity(HikvisionImageEntity):
    """Base class for the entities of an image setting with a list of choices."""

    def __init__(
        self,
        coordinator: HikvisionImageCoordinator,
        entry: HikvisionConfigEntry,
        description: EntityDescription,
        setting: ImageSetting,
        options: dict[str, str],
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entry, description, setting.path)
        self._setting = setting
        self._value_by_option = options
        # The camera may report a value in another case than it lists it in
        self._option_by_value = {
            value.lower(): option for option, value in options.items()
        }

    @property
    @override
    def _reported(self) -> bool:
        """Return whether the camera reports the mode, or the flag it is linked to.

        The camera leaves the mode out while the flag is off.
        """
        enabled_path = self._setting.linked_enabled_path
        return super()._reported or (
            enabled_path is not None and enabled_path in self.coordinator.data
        )

    @property
    def _current_option(self) -> str | None:
        """Return the option of the current value, or None if it is not one."""
        value = self._value
        if (enabled_path := self._setting.linked_enabled_path) is not None:
            # The mode is missing while the feature is off. A flag that the camera
            # does not report, or reports as neither true nor false, says nothing:
            # it must not hide an active mode.
            enabled = self.coordinator.data.get(enabled_path)
            if enabled is not None and enabled.lower() == "false":
                value = self._setting.off_value
        if value is None:
            return None
        return self._option_by_value.get(value.lower())
