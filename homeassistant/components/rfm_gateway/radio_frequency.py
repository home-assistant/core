"""Radio frequency transmitter platform for RFM Gateway."""
from typing import TYPE_CHECKING

from homeassistant.components.radio_frequency import RadioFrequencyTransmitterEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

if TYPE_CHECKING:
    from rf_protocols import RadioFrequencyCommand

from . import RuntimeData
from .client import RfmGatewayConnectionError, RfmGatewayProtocolError
from .const import CONF_HOST, DOMAIN


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the RFM Gateway radio frequency platform."""
    async_add_entities([RfmGatewayTransmitter(entry)])


class RfmGatewayTransmitter(RadioFrequencyTransmitterEntity):
    """Entity representing a gateway-backed RF transmitter."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the RFM transmitter entity."""
        self._entry = entry
        data: RuntimeData = entry.runtime_data
        self._client = data.client
        self._caps = data.capabilities

        host = entry.data[CONF_HOST]
        name = self._caps.device_name or "RFM Gateway"
        config_unique_id = entry.unique_id or host

        self._attr_unique_id = f"{config_unique_id}_rf_tx"
        self._attr_name = "Radio Frequency Transmitter"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_unique_id)},
            name=name,
            manufacturer="Seegel Systeme",
            model="RFM Gateway",
            configuration_url=self._client.base_url,
        )
        self._attr_available = True
        self._host = host

    @property
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        """Return supported frequency ranges in Hz."""
        return self._caps.supported_frequency_ranges

    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Send one RF command through the gateway."""
        availability_changed = not self._attr_available
        modulation = _modulation_to_str(command.modulation)
        if modulation not in self._caps.supported_modulations:
            raise HomeAssistantError(
                f"Gateway does not support modulation '{modulation}', "
                f"supported: {', '.join(self._caps.supported_modulations)}"
            )

        try:
            await self._client.async_send_raw(
                frequency_hz=command.frequency,
                modulation=modulation,
                repeat_count=command.repeat_count,
                timings_us=command.get_raw_timings(),
            )
            self._attr_available = True
            if availability_changed:
                self.async_write_ha_state()
        except (RfmGatewayConnectionError, RfmGatewayProtocolError) as err:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"RF transmit via {self._host} failed: {err}"
            ) from err


def _modulation_to_str(modulation) -> str:
    """Normalize modulation values to a lowercase text token."""
    value = getattr(modulation, "value", modulation)
    text = str(value)
    if "." in text:
        text = text.rsplit(".", maxsplit=1)[-1]
    return text.strip().lower()


def _format_frequency_ranges(ranges: list[tuple[int, int]]) -> str:
    """Format frequency ranges for display."""
    if not ranges:
        return ""
    parts = [f"{lo / 1_000_000:.0f}-{hi / 1_000_000:.0f} MHz" for lo, hi in ranges]
    return ", ".join(parts)
