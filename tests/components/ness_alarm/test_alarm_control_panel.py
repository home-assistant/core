"""Test the Ness Alarm control panel."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.components.ness_alarm.const import DOMAIN
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    SERVICE_ALARM_DISARM,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
        },
    )


@pytest.fixture
def mock_client():
    """Create a mock Ness client."""
    client = AsyncMock()
    client.disarm = AsyncMock()
    client.arm_away = AsyncMock()
    client.arm_home = AsyncMock()
    client.panic = AsyncMock()
    client.keepalive = AsyncMock()
    client.update = AsyncMock()
    client.close = AsyncMock()
    return client


async def test_alarm_control_panel_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test alarm control panel setup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state is not None
    assert state.name == "Alarm Panel"


async def test_alarm_control_panel_disarm(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test disarm."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
        blocking=True,
    )

    mock_client.disarm.assert_called_once_with("1234")
