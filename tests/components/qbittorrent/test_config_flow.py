"""Test the qBittorrent config flow."""
import pytest
from requests.exceptions import RequestException
import requests_mock

from homeassistant.components.qbittorrent.const import (
    CONF_CREATE_TORRENT_SENSORS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
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

USER_INPUT = {
    CONF_URL: "http://localhost:8080",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_VERIFY_SSL: True,
}

YAML_IMPORT = {
    CONF_URL: "http://localhost:8080",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}


async def test_flow_user(hass: HomeAssistant, mock_api: requests_mock.Mocker) -> None:
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
            f"{USER_INPUT[CONF_URL]}/api/v2/app/preferences",
            exc=RequestException,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # Test flow with wrong creds, fail with invalid_auth
    with requests_mock.Mocker() as mock:
        mock.get(f"{USER_INPUT[CONF_URL]}/api/v2/transfer/speedLimitsMode")
        mock.get(f"{USER_INPUT[CONF_URL]}/api/v2/app/preferences", status_code=403)
        mock.post(
            f"{USER_INPUT[CONF_URL]}/api/v2/auth/login",
            text="Wrong username/password",
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    # Test flow with proper input, succeed
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_URL: "http://localhost:8080",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_VERIFY_SSL: True,
    }


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)

    # Open flow as USER with no input
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test flow with duplicate config
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_qbittorrent_options(hass: HomeAssistant) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Enable the torrent_sensors option.
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "qbittorrent_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CREATE_TORRENT_SENSORS: True}
    )

    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert config_entry.options[CONF_CREATE_TORRENT_SENSORS]

    # Disable the torrent_sensors option.
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "qbittorrent_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CREATE_TORRENT_SENSORS: False}
    )

    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert not config_entry.options[CONF_CREATE_TORRENT_SENSORS]
