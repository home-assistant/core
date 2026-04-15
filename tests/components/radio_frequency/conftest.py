"""Common fixtures for the Radio Frequency tests."""

from typing import override

import pytest
from rf_protocols import ModulationType, RadioFrequencyCommand, Timing

from homeassistant.components.radio_frequency import RadioFrequencyTransmitterEntity
from homeassistant.components.radio_frequency.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
async def init_integration(hass: HomeAssistant) -> None:
    """Set up the Radio Frequency integration for testing."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


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
    def get_raw_timings(self) -> list[Timing]:
        """Return mock timings."""
        return [Timing(high_us=350, low_us=1050), Timing(high_us=350, low_us=350)]


class MockRadioFrequencyEntity(RadioFrequencyTransmitterEntity):
    """Mock radio frequency entity for testing."""

    _attr_has_entity_name = True
    _attr_name = "Test RF transmitter"

    def __init__(self, unique_id: str) -> None:
        """Initialize mock entity."""
        self._attr_unique_id = unique_id
        self.send_command_calls: list[RadioFrequencyCommand] = []

    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Mock send command."""
        self.send_command_calls.append(command)


class MockRadioFrequencyEntityWithRanges(MockRadioFrequencyEntity):
    """Mock radio frequency entity with frequency ranges."""

    @property
    def supported_frequency_ranges(self) -> list[tuple[int, int]] | None:
        """Return supported frequency ranges."""
        return [(433_000_000, 434_000_000)]


@pytest.fixture
def mock_rf_entity() -> MockRadioFrequencyEntity:
    """Return a mock radio frequency entity."""
    return MockRadioFrequencyEntity("test_rf_transmitter")


@pytest.fixture
def mock_rf_entity_with_ranges() -> MockRadioFrequencyEntityWithRanges:
    """Return a mock radio frequency entity with frequency ranges."""
    return MockRadioFrequencyEntityWithRanges("test_rf_transmitter_ranged")
