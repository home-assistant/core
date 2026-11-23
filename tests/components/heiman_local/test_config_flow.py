"""Test the manual Heiman Local config flow."""

import pytest

from homeassistant.components.heiman_local.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import WiFiSwitch


async def test_duplicate_switch(
    hass: HomeAssistant, entry: ConfigEntry, device: WiFiSwitch
) -> None:
    """Detect a duplicate switch after receiving the MAC in a different format."""
    device.mac = "a8-c1-d6-01-02-03"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], device.address
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]


@pytest.mark.parametrize(
    ("changes", "overrides", "errors"),
    [
        pytest.param(
            {},
            {CONF_HOST: "http://127.0.0.1"},
            {CONF_HOST: "invalid_host"},
            id="invalid-address",
        ),
        pytest.param(
            {"schema": "different"},
            {},
            {"base": "unsupported_device"},
            id="unsupported-protocol",
        ),
        pytest.param(
            {"online": False}, {}, {"base": "cannot_connect"}, id="unavailable"
        ),
    ],
)
async def test_setup_form_errors(
    hass: HomeAssistant,
    device: WiFiSwitch,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, bool | str],
    overrides: dict[str, str],
    errors: dict[str, str],
) -> None:
    """Keep the form available after invalid input or an incompatible device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    with monkeypatch.context() as patch:
        for attribute, value in changes.items():
            patch.setattr(device, attribute, value)
        result = await hass.config_entries.flow.async_configure(
            flow_id, {**device.address, **overrides}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == errors
        assert not hass.config_entries.async_entries(DOMAIN)

    result = await hass.config_entries.flow.async_configure(flow_id, device.address)
    assert result["type"] is FlowResultType.CREATE_ENTRY
