"""Test the Uptime Robot init."""
from unittest.mock import patch

from pytest import LogCaptureFixture
from pyuptimerobot import UptimeRobotApiResponse
from pyuptimerobot.exceptions import UptimeRobotAuthenticationException

from homeassistant import config_entries
from homeassistant.components.uptimerobot.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_reauthentication_trigger(hass: HomeAssistant, caplog: LogCaptureFixture):
    """Test reauthentication trigger."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=UptimeRobotApiResponse.from_dict(
            {
                "stat": "ok",
                "account": {"email": "test@test.test", "user_id": 1234567890},
            }
        ),
    ), patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        side_effect=UptimeRobotAuthenticationException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "1234"},
        )
        await hass.async_block_till_done()

        assert result2["type"] == RESULT_TYPE_CREATE_ENTRY

        config_entry = hass.config_entries.async_entries(DOMAIN)[0]

        assert config_entry.entry_id == result2["result"].entry_id
        assert config_entry.unique_id == "1234567890"
        assert config_entry.state == config_entries.ConfigEntryState.SETUP_ERROR
        assert config_entry.reason == "could not authenticate"

        flows = [
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["handler"] == DOMAIN
        ]
        assert len(list(flows)) == 1

        config_flow = flows.pop()

        assert config_flow["step_id"] == "reauth_confirm"
        assert config_flow["context"] == {
            "source": "reauth",
            "entry_id": config_entry.entry_id,
            "unique_id": config_entry.unique_id,
        }
        assert (
            "Config entry 'test@test.test' for uptimerobot integration could not authenticate"
            in caplog.text
        )
