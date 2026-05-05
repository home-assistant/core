"""Base entity class for Arcam Solo."""

from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import ArcamSoloConfigEntry
from .const import DOMAIN


class ArcamSoloEntity(Entity):
    """Base entity class for Arcam Solo."""

    def __init__(self, entry: ArcamSoloConfigEntry, entity_key: str) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.arcam_solo = entry.runtime_data
        self.entity_key = entity_key
        self._attr_unique_id = f"{entry.entry_id}_{entity_key}"
        self._attr_translation_key = entity_key

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.arcam_solo.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            manufacturer="Arcam",
            model="Solo",
            name=self.entry.data[CONF_NAME],
            sw_version=self.arcam_solo.zones.get(1, {}).get(
                "software_version", "Unknown"
            ),
            hw_version=self.arcam_solo.zones.get(1, {}).get("rs232_version", "Unknown"),
        )
