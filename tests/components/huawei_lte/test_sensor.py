"""Huawei LTE sensor tests."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.huawei_lte import sensor
from homeassistant.components.huawei_lte.const import DOMAIN, KEY_DEVICE_SIGNAL
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONF_URL,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    Platform,
    UnitOfFrequency,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import magic_client


async def test_signal_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test setup creates the signal sensors with formatted states and units."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://huawei-lte"})
    config_entry.add_to_hass(hass)
    client = magic_client()

    with (
        patch("homeassistant.components.huawei_lte.Connection", MagicMock()),
        patch("homeassistant.components.huawei_lte.Client", return_value=client),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    expected = {
        "ncgi": ("00101ABCDEFABCD", None),
        "nrdlfreq": ("3500.0", UnitOfFrequency.MEGAHERTZ),
        "nrulfreq": ("1800.0", UnitOfFrequency.MEGAHERTZ),
        "scc_pci": ("456", None),
    }
    for key, (expected_state, expected_unit) in expected.items():
        entity_id = entity_registry.async_get_entity_id(
            Platform.SENSOR,
            DOMAIN,
            f"{config_entry.unique_id}-{KEY_DEVICE_SIGNAL}.{key}",
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state
        assert state.attributes.get("unit_of_measurement") == expected_unit
        if expected_unit is UnitOfFrequency.MEGAHERTZ:
            assert state.attributes.get("device_class") == SensorDeviceClass.FREQUENCY


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("-71 dBm", (-71, SIGNAL_STRENGTH_DECIBELS_MILLIWATT)),
        ("15dB", (15, SIGNAL_STRENGTH_DECIBELS)),
        (">=-51dBm", (-51, SIGNAL_STRENGTH_DECIBELS_MILLIWATT)),
        ("&lt;-20dB", (-20, SIGNAL_STRENGTH_DECIBELS)),
        ("&gt;=30dB", (30, SIGNAL_STRENGTH_DECIBELS)),
    ],
)
def test_format_default(value, expected) -> None:
    """Test that default formatter copes with expected values."""
    assert sensor.format_default(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, (None, UnitOfFrequency.MEGAHERTZ)),
        (1234, (1.234, UnitOfFrequency.MEGAHERTZ)),
        ("1234kHz", (1.234, UnitOfFrequency.MEGAHERTZ)),
        (" 123456 kHz ", (123.456, UnitOfFrequency.MEGAHERTZ)),
        ("5000 kHz", (5.0, UnitOfFrequency.MEGAHERTZ)),
        ("abc", (None, UnitOfFrequency.MEGAHERTZ)),
    ],
)
def test_format_freq_khz(value, expected) -> None:
    """Test that frequency formatter copes with expected values."""
    assert sensor.format_freq_khz(value) == expected


@pytest.mark.parametrize(
    ("value", "expected_elapsed"),
    [
        ("0", timedelta(0)),
        ("90", timedelta(seconds=90)),
        ("86400", timedelta(days=1)),
    ],
)
def test_format_last_reset_elapsed_seconds(
    freezer: FrozenDateTimeFactory, value: str, expected_elapsed: timedelta
) -> None:
    """Test elapsed seconds are turned into an aware, truncated reset time."""
    freezer.move_to("2026-01-02T03:04:05.678901+00:00")

    result = sensor.format_last_reset_elapsed_seconds(value)

    assert result is not None
    assert result.tzinfo is not None
    assert result.microsecond == 0
    assert result == dt_util.utcnow().replace(microsecond=0) - expected_elapsed


@pytest.mark.parametrize("value", [None, "", "not a number"])
def test_format_last_reset_elapsed_seconds_invalid(value: str | None) -> None:
    """Test values that cannot be converted are ignored."""
    assert sensor.format_last_reset_elapsed_seconds(value) is None
