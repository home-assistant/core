"""Test the Uptime Robot init."""
import datetime
from unittest.mock import patch

from pytest import LogCaptureFixture
from pyuptimerobot import UptimeRobotApiResponse
from pyuptimerobot.exceptions import UptimeRobotAuthenticationException

from homeassistant import config_entries
from homeassistant.components.uptimerobot.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_reauthentication_trigger_in_setup(
    hass: HomeAssistant, caplog: LogCaptureFixture
):
    """Test reauthentication trigger."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="test@test.test",
        data={"platform": DOMAIN, "api_key": "1234"},
        unique_id="1234567890",
        source=config_entries.SOURCE_USER,
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        side_effect=UptimeRobotAuthenticationException,
    ):

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()

    assert mock_config_entry.state == config_entries.ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "could not authenticate"

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH
    assert flow["context"]["entry_id"] == mock_config_entry.entry_id

    assert (
        "Config entry 'test@test.test' for uptimerobot integration could not authenticate"
        in caplog.text
    )


async def test_reauthentication_trigger_after_setup(
    hass: HomeAssistant, caplog: LogCaptureFixture
):
    """Test reauthentication trigger."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="test@test.test",
        data={"platform": DOMAIN, "api_key": "1234"},
        unique_id="1234567890",
        source=config_entries.SOURCE_USER,
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        return_value=UptimeRobotApiResponse.from_dict(
            {
                "stat": "ok",
                "monitors": [
                    {"id": 1234, "friendly_name": "Test monitor", "status": 2}
                ],
            }
        ),
    ):

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    binary_sensor = hass.states.get("binary_sensor.test_monitor")
    assert mock_config_entry.state == config_entries.ConfigEntryState.LOADED
    assert binary_sensor.state == "on"

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        side_effect=UptimeRobotAuthenticationException,
    ):

        async_fire_time_changed(hass, dt.utcnow() + datetime.timedelta(seconds=10))
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    binary_sensor = hass.states.get("binary_sensor.test_monitor")

    assert binary_sensor.state == "unavailable"
    assert "Authentication failed while fetching uptimerobot data" in caplog.text

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH
    assert flow["context"]["entry_id"] == mock_config_entry.entry_id
