"""Tests for the GogoGate2 component."""
from unittest.mock import MagicMock, patch

from ismartgate import GogoGate2Api
from ismartgate.common import ApiError
from ismartgate.const import GogoGate2ApiErrorCode

from homeassistant import config_entries, setup
from homeassistant.components.gogogate2.const import (
    DEVICE_TYPE_GOGOGATE2,
    DEVICE_TYPE_ISMARTGATE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_FORM

from tests.common import MockConfigEntry

MOCK_MAC_ADDR = "AA:BB:CC:DD:EE:FF"


@patch("homeassistant.components.gogogate2.async_setup_entry", return_value=True)
@patch("homeassistant.components.gogogate2.common.GogoGate2Api")
async def test_auth_fail(
    gogogate2api_mock, async_setup_entry_mock, hass: HomeAssistant
) -> None:
    """Test authorization failures."""
    api: GogoGate2Api = MagicMock(spec=GogoGate2Api)
    gogogate2api_mock.return_value = api

    api.reset_mock()
    api.async_info.side_effect = ApiError(
        GogoGate2ApiErrorCode.CREDENTIALS_INCORRECT, "blah"
    )
    result = await hass.config_entries.flow.async_init(
        "gogogate2", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        },
    )
    assert result
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {
        "base": "invalid_auth",
    }

    api.reset_mock()
    api.async_info.side_effect = Exception("Generic connection error.")
    result = await hass.config_entries.flow.async_init(
        "gogogate2", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        },
    )
    assert result
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_homekit_unique_id_already_setup(hass):
    """Test that we abort from homekit if gogogate2 is already setup."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data={"host": "1.2.3.4", "properties": {"id": MOCK_MAC_ADDR}},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    flow = next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert flow["context"]["unique_id"] == MOCK_MAC_ADDR

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4", CONF_USERNAME: "mock", CONF_PASSWORD: "mock"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data={"host": "1.2.3.4", "properties": {"id": MOCK_MAC_ADDR}},
    )
    assert result["type"] == RESULT_TYPE_ABORT


async def test_form_homekit_ip_address_already_setup(hass):
    """Test that we abort from homekit if gogogate2 is already setup."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4", CONF_USERNAME: "mock", CONF_PASSWORD: "mock"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data={"host": "1.2.3.4", "properties": {"id": MOCK_MAC_ADDR}},
    )
    assert result["type"] == RESULT_TYPE_ABORT


async def test_form_homekit_ip_address(hass):
    """Test homekit includes the defaults ip address."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data={"host": "1.2.3.4", "properties": {"id": MOCK_MAC_ADDR}},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    data_schema = result["data_schema"]
    assert data_schema({CONF_USERNAME: "username", CONF_PASSWORD: "password"}) == {
        CONF_DEVICE: DEVICE_TYPE_ISMARTGATE,
        CONF_IP_ADDRESS: "1.2.3.4",
        CONF_PASSWORD: "password",
        CONF_USERNAME: "username",
    }
