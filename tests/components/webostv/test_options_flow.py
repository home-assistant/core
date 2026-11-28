"""Test the LG webOS TV options flow."""

from unittest.mock import MagicMock

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.webostv.const import (
    CONF_SOURCES,
    CONF_WAKE_ON_LAN,
    DOMAIN,
    LIVE_TV_APP_ID,
)
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_CLIENT_SECRET,
    CONF_HOST,
    CONF_MAC,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv

from . import setup_webostv
from .const import CLIENT_KEY, FAKE_UUID, HOST, MOCK_APPS, MOCK_INPUTS


@pytest.mark.parametrize(
    ("apps", "inputs"),
    [
        # Live TV in apps (default)
        (MOCK_APPS, MOCK_INPUTS),
        # Live TV in inputs
        (
            {},
            {
                **MOCK_INPUTS,
                "livetv": {"label": "Live TV", "id": "livetv", "appId": LIVE_TV_APP_ID},
            },
        ),
        # Live TV not found
        ({}, MOCK_INPUTS),
    ],
)
async def test_options_flow_live_tv_in_apps(
    hass: HomeAssistant, client, apps, inputs
) -> None:
    """Test options config flow Live TV found in apps."""
    client.tv_state.apps = apps
    client.tv_state.inputs = inputs
    entry = await setup_webostv(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SOURCES: ["Live TV", "Input01", "Input02"]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SOURCES] == ["Live TV", "Input01", "Input02"]


async def test_options_flow_not_connected(hass: HomeAssistant, client) -> None:
    """Test options flow when the TV is not connected."""
    entry = await setup_webostv(hass)

    client.is_connected.return_value = False
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # recover
    client.is_connected.return_value = True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=None,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SOURCES: ["Input01", "Input02"]},
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_SOURCES] == ["Input01", "Input02"]


@pytest.mark.usefixtures("client")
async def test_options_flow_entry_not_loaded(hass: HomeAssistant) -> None:
    """Test options flow when the config entry is not loaded."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_CLIENT_SECRET: CLIENT_KEY},
        options={CONF_SOURCES: ["Input01"]},
        unique_id=FAKE_UUID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    # The saved sources stay selectable while the TV is unavailable
    assert result["data_schema"].schema[CONF_SOURCES].options == {"Input01": "Input01"}


async def test_options_flow_no_sources_selected(hass: HomeAssistant, client) -> None:
    """Test options flow when no source is selected."""
    entry = await setup_webostv(hass, options={CONF_SOURCES: ["Input01"]})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_SOURCES: []}


async def test_wake_options(hass: HomeAssistant, client: MagicMock) -> None:
    """Save and clear wake-up overrides while preserving selected sources."""
    entry = await setup_webostv(hass)
    wake_options = {
        CONF_BROADCAST_ADDRESS: "192.168.10.255",
        CONF_MAC: "11:22:33:44:55:66",
    }
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SOURCES: ["Input01"], CONF_WAKE_ON_LAN: wake_options},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {CONF_SOURCES: ["Input01"], CONF_WAKE_ON_LAN: wake_options}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    section = result["data_schema"].schema[CONF_WAKE_ON_LAN]
    assert section.options["collapsed"]
    assert section.schema({}) == {}
    fields = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    wake_field = next(field for field in fields if field["name"] == CONF_WAKE_ON_LAN)
    assert "default" not in wake_field
    assert {
        field["name"]: field["description"]["suggested_value"]
        for field in wake_field["schema"]
    } == wake_options
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SOURCES: ["Input01"], CONF_WAKE_ON_LAN: {}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {CONF_SOURCES: ["Input01"]}


@pytest.mark.parametrize(
    "wake_options",
    [
        pytest.param({CONF_BROADCAST_ADDRESS: "invalid"}, id="invalid-ip"),
        pytest.param({CONF_BROADCAST_ADDRESS: "::1"}, id="ipv6"),
        pytest.param({CONF_MAC: "not-a-mac"}, id="invalid-mac"),
    ],
)
async def test_invalid_wake_options(
    hass: HomeAssistant, client: MagicMock, wake_options: dict[str, str]
) -> None:
    """Reject invalid wake-up addresses before saving options."""
    entry = await setup_webostv(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(probatio.Invalid):
        result["data_schema"]({CONF_WAKE_ON_LAN: wake_options})
