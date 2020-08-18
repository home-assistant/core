"""The tests the cover command line platform."""
import os
import tempfile
from unittest import mock

import pytest

import homeassistant.components.command_line.cover as cmd_rs
from homeassistant.components.cover import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.setup import async_setup_component


@pytest.fixture
def rs(hass):
    """Return CommandCover instance."""
    return cmd_rs.CommandCover(
        hass,
        "foo",
        "command_open",
        "command_close",
        "command_stop",
        "command_state",
        None,
        15,
    )


def test_should_poll_new(rs):
    """Test the setting of polling."""
    assert rs.should_poll is True
    rs._command_state = None
    assert rs.should_poll is False


def test_query_state_value(rs):
    """Test with state value."""
    with mock.patch("subprocess.check_output") as mock_run:
        mock_run.return_value = b" foo bar "
        result = rs._query_state_value("runme")
        assert "foo bar" == result
        assert mock_run.call_count == 1
        assert mock_run.call_args == mock.call(
            "runme", shell=True, timeout=15  # nosec # shell by design
        )


async def test_state_value(hass):
    """Test with state value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "cover_status")
        test_cover = {
            "command_state": f"cat {path}",
            "command_open": f"echo 1 > {path}",
            "command_close": f"echo 1 > {path}",
            "command_stop": f"echo 0 > {path}",
            "value_template": "{{ value }}",
        }
        assert (
            await async_setup_component(
                hass,
                DOMAIN,
                {"cover": {"platform": "command_line", "covers": {"test": test_cover}}},
            )
            is True
        )
        await hass.async_block_till_done()

        assert "unknown" == hass.states.get("cover.test").state

        await hass.services.async_call(
            DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
        )
        assert "open" == hass.states.get("cover.test").state

        await hass.services.async_call(
            DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
        )
        assert "open" == hass.states.get("cover.test").state

        await hass.services.async_call(
            DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
        )
        assert "closed" == hass.states.get("cover.test").state
