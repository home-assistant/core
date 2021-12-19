"""Tests for the Agent DVR alarm control panel."""
from typing import Optional
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.agent_dvr.alarm_control_panel import AgentBaseStation


def client_mock(profile: Optional[str] = "home"):
    """Use this to mock the agent client."""
    api = Mock()
    api.update = AsyncMock()
    api.get_active_profile = AsyncMock(return_value=profile)
    return api


async def test_update():
    """Test update happy path."""
    with patch("homeassistant.components.agent_dvr"):
        api = client_mock()
        alarm = AgentBaseStation(api)
        await alarm.async_update()
        assert alarm.state == "armed_home"


async def test_update_none_profile():
    """Test update none profile."""
    with patch("homeassistant.components.agent_dvr"):
        api = client_mock(None)
        alarm = AgentBaseStation(api)
        await alarm.async_update()
        assert alarm.state == "armed_away"
