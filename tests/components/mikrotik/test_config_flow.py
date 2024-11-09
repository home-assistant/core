"""Test Mikrotik setup process."""

from unittest.mock import patch

import librouteros
import pytest

from homeassistant import config_entries
from homeassistant.components.mikrotik.const import (
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_FORCE_DHCP,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DEMO_USER_INPUT = {
    CONF_HOST: "0.0.0.0",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 8278,
    CONF_VERIFY_SSL: False,
}

DEMO_CONFIG_ENTRY = {
    CONF_HOST: "0.0.0.0",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 8278,
    CONF_VERIFY_SSL: False,
    CONF_FORCE_DHCP: False,
    CONF_ARP_PING: False,
    CONF_DETECTION_TIME: 30,
}


@pytest.fixture(name="api")
def mock_mikrotik_api():
    """Mock an api."""
    with patch("librouteros.connect"):
        yield


@pytest.fixture(name="auth_error")
def mock_api_authentication_error():
    """Mock an api."""
    with patch(
        "librouteros.connect",
        side_effect=librouteros.exceptions.TrapError("invalid user name or password"),
    ):
        yield


@pytest.fixture(name="conn_error")
def mock_api_connection_error():
    """Mock an api."""
    with patch(
        "librouteros.connect", side_effect=librouteros.exceptions.ConnectionClosed
    ):
        yield


async def test_flow_works(hass: HomeAssistant, api) -> None:
    """Test config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mikrotik (0.0.0.0)"
    assert result["data"][CONF_HOST] == "0.0.0.0"
    assert result["data"][CONF_USERNAME] == "username"
    assert result["data"][CONF_PASSWORD] == "password"
    assert result["data"][CONF_PORT] == 8278


async def test_options(hass: HomeAssistant, api) -> None:
    """Test updating options."""
    entry = MockConfigEntry(domain=DOMAIN, data=DEMO_CONFIG_ENTRY)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_tracker"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DETECTION_TIME: 30,
            CONF_ARP_PING: True,
            CONF_FORCE_DHCP: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_DETECTION_TIME: 30,
        CONF_ARP_PING: True,
        CONF_FORCE_DHCP: False,
    }


async def test_host_already_configured(hass: HomeAssistant, auth_error) -> None:
    """Test host already configured."""

    entry = MockConfigEntry(domain=DOMAIN, data=DEMO_CONFIG_ENTRY)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_connection_error(hass: HomeAssistant, conn_error) -> None:
    """Test error when connection is unsuccessful."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_wrong_credentials(hass: HomeAssistant, auth_error) -> None:
    """Test error when credentials are wrong."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_USERNAME: "invalid_auth",
        CONF_PASSWORD: "invalid_auth",
    }


async def test_reauth_success(hass: HomeAssistant, api) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEMO_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        CONF_NAME: "Mock Title",
        CONF_USERNAME: "username",
    }

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-password",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauth_failed(hass: HomeAssistant, auth_error) -> None:
    """Test reauth fails due to wrong password."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEMO_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-wrong-password",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {
        CONF_PASSWORD: "invalid_auth",
    }


async def test_reauth_failed_conn_error(hass: HomeAssistant, conn_error) -> None:
    """Test reauth failed due to connection error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEMO_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-wrong-password",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
