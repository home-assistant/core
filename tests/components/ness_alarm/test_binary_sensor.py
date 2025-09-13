"""Test the Ness Alarm binary sensors."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.ness_alarm import SIGNAL_ZONE_CHANGED
from homeassistant.components.ness_alarm.const import CONF_MAX_SUPPORTED_ZONES, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import dispatcher

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            CONF_MAX_SUPPORTED_ZONES: 2,
        },
    )


@pytest.fixture
def mock_client():
    """Create a mock Ness client."""
    client = AsyncMock()
    client.keepalive = AsyncMock()
    client.update = AsyncMock()
    client.close = AsyncMock()
    return client


async def test_binary_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test binary sensor setup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check that 2 zones were created
    state1 = hass.states.get("binary_sensor.zone_1")
    assert state1 is not None
    assert state1.name == "Zone 1"
    assert state1.state == STATE_OFF

    state2 = hass.states.get("binary_sensor.zone_2")
    assert state2 is not None
    assert state2.name == "Zone 2"
    assert state2.state == STATE_OFF


async def test_zone_state_changes(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test zone state changes."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Initial state
    assert hass.states.get("binary_sensor.zone_1").state == STATE_OFF
    assert hass.states.get("binary_sensor.zone_2").state == STATE_OFF

    # Trigger zone 1 via dispatcher directly
    dispatcher.async_dispatcher_send(hass, SIGNAL_ZONE_CHANGED, 1, True)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.zone_1").state == STATE_ON
    assert hass.states.get("binary_sensor.zone_2").state == STATE_OFF
