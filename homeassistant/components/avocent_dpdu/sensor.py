"""Support for Avocent DPDU Sensors."""

from decimal import Decimal

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AvocentDpduDataUpdateCoordinator
from .entity import CurrentEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile switches from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([AvocentDPDUSensorEntity(coordinator)])


class AvocentDPDUSensorEntity(CurrentEntity, SensorEntity):
    """Avocent Direct PDU entity reporting overall status."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AvocentDpduDataUpdateCoordinator,
    ) -> None:
        """Initialize the platform."""

        super().__init__(coordinator)

        self._attr_name = "Total Current"
        self._attr_unique_id = f"{format_mac(coordinator.api.mac)}-current"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_suggested_display_precision = 1
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def should_poll(self) -> bool:
        """The AvocentDpduDataUpdateCoordinator will handle updates."""
        return False

    @property
    def native_value(self) -> Decimal:
        """Return the current value of the current sensor."""
        return Decimal(self.coordinator.api.get_current_deciamps()) / 10

    @property
    def icon(self) -> str:
        """Return a representative icon."""
        status = self.coordinator.api.get_pdu_status_integer()
        icon = "mdi:current-ac"  # Normal icon
        if status == 1:
            icon = "mdi:alert"  # Warning: approaching overload
        elif status == 2:
            icon = "mdi:electric-switch"  # Overloaded and turned off
        return icon
