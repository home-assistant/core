"""Tests for the diagnostics data provided by the TP-Link integration."""
from collections.abc import Mapping
import json

from aiohttp import ClientSession

from homeassistant.components.tplink.diagnostics import TO_REDACT
from homeassistant.core import HomeAssistant

from . import _mocked_bulb, initialize_config_entry_for_device

from tests.common import load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
):
    """Test diagnostics for config entry."""
    diagnostics_data = json.loads(
        load_fixture("tplink-diagnostics-data-bulb-kl130.json", "tplink")
    )

    dev = _mocked_bulb()
    dev._last_update = diagnostics_data["device_last_response"]

    config_entry = await initialize_config_entry_for_device(hass, dev)
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert isinstance(result, dict)
    assert "device_last_response" in result

    # There must be some redactions in place, so the raw data must not match
    assert result["device_last_response"] != diagnostics_data["device_last_response"]

    last_response = result["device_last_response"]

    # Check that we have at least get_sysinfo results we can verify to be redacted
    assert "system" in last_response
    assert "get_sysinfo" in last_response["system"]

    def _check_if_redacted(c, to_redact):
        for k, v in c.items():
            if isinstance(v, Mapping):
                return _check_if_redacted(v, to_redact)
            if k in to_redact:
                assert v == "**REDACTED**"

    _check_if_redacted(last_response, TO_REDACT)
