"""Tests for rpi_power diagnostics."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from rpi_bad_power import (
    RpiBadPowerError,
    ThrottledStatus,
    UnderVoltageLegacy,
    UnderVoltageNew,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rpi_power.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_diagnostics_new(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics with modern raspberrypi-hwmon reader."""
    client = UnderVoltageNew("/sys/class/hwmon/hwmon0")
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.rpi_power.new_under_voltage",
            return_value=client,
        ),
        patch.object(UnderVoltageNew, "get", return_value=False),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot


async def test_diagnostics_legacy(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics with legacy get_throttled reader."""
    client = UnderVoltageLegacy()
    throttled_status = ThrottledStatus.from_hex("0x50005")
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.rpi_power.new_under_voltage",
            return_value=client,
        ),
        patch.object(
            UnderVoltageLegacy,
            "get_throttled_status",
            return_value=throttled_status,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot


async def test_diagnostics_read_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics when reading sysfs raises an error."""
    client = UnderVoltageLegacy()
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.rpi_power.new_under_voltage",
            return_value=client,
        ),
        patch.object(
            UnderVoltageLegacy,
            "get_throttled_status",
            return_value=ThrottledStatus.from_hex("0"),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    with patch.object(
        UnderVoltageLegacy,
        "get_throttled_status",
        side_effect=RpiBadPowerError("I/O error"),
    ):
        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot
