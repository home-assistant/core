from __future__ import annotations

from dataclasses import dataclass

from rf_protocols import RadioFrequencyCommand

from homeassistant.components.radio_frequency import RadioFrequencyTransmitterEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import (
    RfmCapabilities,
    RfmGatewayClient,
    RfmGatewayConnectionError,
    RfmGatewayProtocolError,
)
from .config_flow import RfmGatewayConfigFlow
from .const import CONF_HOST, DOMAIN


@dataclass(slots=True)
class RuntimeData:
    client: RfmGatewayClient
    capabilities: RfmCapabilities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    host = entry.data[CONF_HOST]

    base_url = RfmGatewayConfigFlow._build_base_url(host)
    client = RfmGatewayClient(
        hass=hass,
        base_url=base_url,
    )

    try:
        capabilities = await client.async_get_capabilities()
    except (RfmGatewayConnectionError, RfmGatewayProtocolError) as err:
        raise HomeAssistantError(f"Could not initialize RFM Gateway at {base_url}: {err}") from err

    entry.runtime_data = RuntimeData(client=client, capabilities=capabilities)
    async_add_entities([RfmGatewayTransmitter(entry)])


class RfmGatewayTransmitter(RadioFrequencyTransmitterEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        data: RuntimeData = entry.runtime_data
        self._client = data.client
        self._caps = data.capabilities

        host = entry.data[CONF_HOST]
        name = self._caps.device_name or "RFM Gateway"

        self._attr_unique_id = f"{entry.entry_id}_rf_tx"
        self._attr_name = "Radio Frequency Transmitter"
        freq_ranges = _format_frequency_ranges(self._caps.supported_frequency_ranges)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=name,
            manufacturer="Seegel Systeme",
            model="RFM Gateway",
            hw_version=freq_ranges or None,
            configuration_url=self._client.base_url,
        )
        self._attr_available = True
        self._host = host

    @property
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        return self._caps.supported_frequency_ranges

    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
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
        except (RfmGatewayConnectionError, RfmGatewayProtocolError) as err:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(f"RF transmit via {self._host} failed: {err}") from err


def _modulation_to_str(modulation) -> str:
    value = getattr(modulation, "value", modulation)
    text = str(value)
    if "." in text:
        text = text.split(".")[-1]
    return text.strip().lower()


def _format_frequency_ranges(ranges: list[tuple[int, int]]) -> str:
    if not ranges:
        return ""
    parts = [f"{lo / 1_000_000:.0f}-{hi / 1_000_000:.0f} MHz" for lo, hi in ranges]
    return ", ".join(parts)