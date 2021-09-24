"""NINA sensor platform."""
from typing import Any, Dict, List

from pynina import ApiError, Nina, Warning

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    _LOGGER,
    CONF_FILTER_CORONA,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    DOMAIN,
    SCAN_INTERVAL,
)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Any
) -> None:
    """Set up entries."""
    config: Dict[str, Any] = hass.data[DOMAIN][config_entry.entry_id]

    regions: Dict[str, str] = config[CONF_REGIONS]

    filterCorona: bool = config[CONF_FILTER_CORONA]

    nina: Nina = Nina()

    for region in regions.keys():
        nina.addRegion(region)

    async def async_update_data():
        """Fetch data from NINA."""
        try:
            await nina.update()

            return nina.warnings

        except ApiError as err:
            _LOGGER.warning(f"NINA connection error: {err}")

    coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    entities: List[Message] = []

    for idx, ent in enumerate(coordinator.data):
        r: str = ent
        for i in range(0, config[CONF_MESSAGE_SLOTS]):
            entities.append(Message(coordinator, r, regions[r], i + 1, filterCorona))

    async_add_entities(entities)


class Message(CoordinatorEntity, BinarySensorEntity):
    """Representation of an NINA warning."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        region: str,
        regionName: str,
        slotID: int,
        filterCorona: bool,
    ):
        """Initialize."""
        super().__init__(coordinator)

        self._region: str = region
        self._regionName: str = regionName
        self._hasWarning: bool = False
        self._slotID: int = slotID

        self._messageID: str = ""
        self._messageHeading: str = ""
        self._messageSent: str = ""
        self._messageStart: str = ""
        self._messageExpires: str = ""

        self._filterCorona: bool = filterCorona

        self._coordinator: DataUpdateCoordinator = coordinator

        self.parseUpdate()

    def parseUpdate(self):
        """Parse data from coordinator."""
        warnings: List[Warning] = self._coordinator.data[self._region]

        warningIndex: int = self._slotID - 1

        if len(warnings) > warningIndex:
            warning: Warning = warnings[warningIndex]
            self._messageID = warning.id
            self._messageHeading = warning.headline

            self._messageSent = warning.sent or ""
            self._messageStart = warning.start or ""
            self._messageExpires = warning.expires or ""

            self._hasWarning = True

            filter: bool = (
                "corona" in self._messageHeading.lower() and self._filterCorona
            )

            if warning.isValid() and not filter:
                return

        self._messageID = ""
        self._messageHeading = ""

        self._hasWarning = False

        self._messageSent = ""
        self._messageStart = ""
        self._messageExpires = ""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Warnung: {self._regionName} {self._slotID}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        self.parseUpdate()
        return self._hasWarning

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra attributes of the sensor."""
        self.parseUpdate()

        attributes: Dict[str, Any] = {
            "Headline": self._messageHeading,
            "ID": self._messageID,
            "Sent": self._messageSent,
            "Start": self._messageStart,
            "Expires": self._messageExpires,
        }

        return attributes

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self._region}-{self._slotID}"

    @property
    def device_class(self) -> str:
        """Return the device class of this entity."""
        return "safety"
