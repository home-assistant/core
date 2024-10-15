"""Test binary sensors of APCUPSd integration."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from . import MOCK_STATUS, async_init_integration


async def test_binary_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test states of binary sensor."""
    await async_init_integration(hass, status=MOCK_STATUS)

    device_slug, serialno = slugify(MOCK_STATUS["UPSNAME"]), MOCK_STATUS["SERIALNO"]
    state = hass.states.get(f"binary_sensor.{device_slug}_online_status")
    assert state
    assert state.state == "on"
    entry = entity_registry.async_get(f"binary_sensor.{device_slug}_online_status")
    assert entry
    assert entry.unique_id == f"{serialno}_statflag"


async def test_no_binary_sensor(hass: HomeAssistant) -> None:
    """Test binary sensor when STATFLAG is not available."""
    status = MOCK_STATUS.copy()
    status.pop("STATFLAG")
    await async_init_integration(hass, status=status)

    device_slug = slugify(MOCK_STATUS["UPSNAME"])
    state = hass.states.get(f"binary_sensor.{device_slug}_online_status")
    assert state is None


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ("0x008", "on"),
        ("0x02040010 Status Flag", "off"),
    ],
)
async def test_statflag(hass: HomeAssistant, override: str, expected: str) -> None:
    """Test binary sensor for different STATFLAG values."""
    status = MOCK_STATUS.copy()
    status["STATFLAG"] = override
    await async_init_integration(hass, status=status)

    device_slug = slugify(MOCK_STATUS["UPSNAME"])
    assert (
        hass.states.get(f"binary_sensor.{device_slug}_online_status").state == expected
    )
