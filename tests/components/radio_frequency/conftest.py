"""Common fixtures for the Radio Frequency tests."""

from typing import NamedTuple, override

import pytest
from rf_protocols import ModulationType, RadioFrequencyCommand

from homeassistant.components.radio_frequency import (
    DATA_COMPONENT,
    RadioFrequencyTransmitterEntity,
)
from homeassistant.components.radio_frequency.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
async def init_integration(hass: HomeAssistant) -> None:
    """Set up the Radio Frequency integration for testing."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


class MockCommand(NamedTuple):
    """Data structure to store calls to async_send_command."""

    command: RadioFrequencyCommand
    context: object | None


class MockRadioFrequencyCommand(RadioFrequencyCommand):
    """Mock RF command for testing."""

    def __init__(
        self,
        *,
        frequency: int = 433_920_000,
        modulation: ModulationType = ModulationType.OOK,
        repeat_count: int = 0,
    ) -> None:
        """Initialize mock command."""
        super().__init__(
            frequency=frequency, modulation=modulation, repeat_count=repeat_count
        )

    @override
    def get_raw_timings(self) -> list[int]:
        """Return mock timings."""
        return [350, -1050, 350, -350]


class MockRadioFrequencyEntity(RadioFrequencyTransmitterEntity):
    """Mock radio frequency entity for testing."""

    _attr_has_entity_name = True
    _attr_name = "Test RF transmitter"

    def __init__(
        self,
        unique_id: str,
        frequency_ranges: list[tuple[int, int]] | None = None,
    ) -> None:
        """Initialize mock entity."""
        self._attr_unique_id = unique_id
        self._frequency_ranges = (
            [(433_000_000, 434_000_000)]
            if frequency_ranges is None
            else frequency_ranges
        )
        self.send_command_calls: list[MockCommand] = []

    @property
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        """Return supported frequency ranges."""
        return self._frequency_ranges

    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Mock send command."""
        self.send_command_calls.append(
            MockCommand(command=command, context=self._context)
        )


@pytest.fixture
async def mock_rf_entity(
    hass: HomeAssistant, init_integration: None
) -> MockRadioFrequencyEntity:
    """Return a mock radio frequency entity."""
    entity = MockRadioFrequencyEntity("test_rf_transmitter")
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([entity])
    return entity
