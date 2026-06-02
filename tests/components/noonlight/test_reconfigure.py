"""Reconfigure-flow tests (editing caller/location without re-adding)."""

from __future__ import annotations

from httpx import Response
import respx

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.noonlight.const import (
    CONF_LOCATION_ID,
    CONF_PHONE,
    CONF_STATE,
    CONF_ZIP,
    DOMAIN,
)


def _start_reconfigure(hass, entry):
    return hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )


@respx.mock
async def test_reconfigure_updates_caller_and_site(hass, setup_entry):
    # The reconfigure reloads the entry, which re-runs the setup probe.
    respx.get(url__regex=r".*/dispatch/v1/alarms/.*/status").mock(
        return_value=Response(404)
    )
    result = await _start_reconfigure(hass, setup_entry)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Brent",
            # Loose input is normalized on the way in.
            CONF_PHONE: "(202) 555-0142",
            # Address + ZIP are unchanged so the address-based unique id still
            # matches this entry (reconfigure can't change an entry's identity).
            "address": "1 Test St",
            "city": "Springfield",
            CONF_STATE: "va",
            CONF_ZIP: "90001",
            CONF_LOCATION_ID: "Lake House",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert setup_entry.data[CONF_PHONE] == "+12025550142"
    assert setup_entry.data[CONF_STATE] == "VA"
    assert setup_entry.data[CONF_LOCATION_ID] == "Lake House"
    # Untouched secrets are preserved.
    assert setup_entry.data["api_token"] == "test-token"


async def test_reconfigure_rejects_bad_input(hass, setup_entry):
    result = await _start_reconfigure(hass, setup_entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Brent",
            CONF_PHONE: "123",
            "address": "123 Main St",
            "city": "Springfield",
            CONF_STATE: "Virginia",
            CONF_ZIP: "abc",
        },
    )
    assert result["step_id"] == "reconfigure"
    assert result["errors"][CONF_PHONE] == "invalid_phone"
    assert result["errors"][CONF_STATE] == "invalid_state"
    assert result["errors"][CONF_ZIP] == "invalid_zip"
    # Nothing changed on the entry.
    assert setup_entry.data[CONF_STATE] == "CA"
