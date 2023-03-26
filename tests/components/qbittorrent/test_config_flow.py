"""Test the qBittorrent config flow."""
import pytest
from requests.exceptions import RequestException
import requests_mock

from homeassistant.components.qbittorrent.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SOURCE,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

CONFIG_VALID = {
    CONF_URL: "http://localhost:8080",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_VERIFY_SSL: True,
}

CONFIG_INVALID_AUTH = {
    CONF_URL: "http://localhost:8080",
    CONF_USERNAME: "null",
    CONF_PASSWORD: "none",
    CONF_VERIFY_SSL: True,
}

CONFIG_CANNOT_CONNECT = {
    CONF_URL: "http://nowhere:23456",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_VERIFY_SSL: True,
}

CONFIG_IMPORT_VALID = {
    CONF_URL: "http://localhost:8080",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}


async def test_flow_user(hass: HomeAssistant, mock_api) -> None:
    """Test the user flow."""
    # Open flow as USER with no input
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test flow with connection failure, fail with cannot_connect
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{CONFIG_CANNOT_CONNECT[CONF_URL]}/api/v2/app/preferences",
            exc=RequestException,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_CANNOT_CONNECT
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # Test flow with wrong creds, fail with invalid_auth
    with requests_mock.Mocker() as mock:
        mock.get(f"{CONFIG_INVALID_AUTH[CONF_URL]}/api/v2/transfer/speedLimitsMode")
        mock.get(
            f"{CONFIG_INVALID_AUTH[CONF_URL]}/api/v2/app/preferences", status_code=403
        )
        mock.post(
            f"{CONFIG_INVALID_AUTH[CONF_URL]}/api/v2/auth/login",
            text="Wrong username/password",
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_INVALID_AUTH
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    # Test flow with proper input, succeed
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_VALID
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == CONFIG_VALID


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_VALID)
    entry.add_to_hass(hass)

    # Open flow as USER with no input
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test flow with duplicate config
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_VALID
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_import(hass: HomeAssistant) -> None:
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_IMPORT},
        data=CONFIG_IMPORT_VALID,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == CONFIG_VALID


async def test_flow_import_already_configured(hass: HomeAssistant) -> None:
    """Test import step already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_VALID)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_IMPORT},
        data=CONFIG_IMPORT_VALID,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
