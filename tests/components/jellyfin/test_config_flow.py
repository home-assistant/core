"""Test the jellyfin config flow."""
from unittest.mock import MagicMock

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.jellyfin.const import CONF_CLIENT_DEVICE_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import async_load_json_fixture
from .const import TEST_PASSWORD, TEST_URL, TEST_USERNAME

from tests.common import MockConfigEntry


async def test_abort_if_existing_entry(hass: HomeAssistant) -> None:
    """Check flow abort when an entry already exist."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_form(
    hass: HomeAssistant,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
    mock_client_device_id: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test the complete configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "JELLYFIN-SERVER"
    assert result2["data"] == {
        CONF_CLIENT_DEVICE_ID: "TEST-UUID",
        CONF_URL: TEST_URL,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }

    assert len(mock_client.auth.connect_to_address.mock_calls) == 1
    assert len(mock_client.auth.login.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_client.jellyfin.get_user_settings.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
    mock_client_device_id: MagicMock,
) -> None:
    """Test we handle an unreachable server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_client.auth.connect_to_address.return_value = await async_load_json_fixture(
        hass, "auth-connect-address-failure.json"
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}

    assert len(mock_client.auth.connect_to_address.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
    mock_client_device_id: MagicMock,
) -> None:
    """Test that we can handle invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass, "auth-login-failure.json"
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}

    assert len(mock_client.auth.connect_to_address.mock_calls) == 1
    assert len(mock_client.auth.login.mock_calls) == 1


async def test_form_exception(
    hass: HomeAssistant, mock_jellyfin: MagicMock, mock_client: MagicMock
) -> None:
    """Test we handle an unexpected exception during server setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_client.auth.connect_to_address.side_effect = Exception("UnknownException")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}

    assert len(mock_client.auth.connect_to_address.mock_calls) == 1


async def test_form_persists_device_id_on_error(
    hass: HomeAssistant,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
    mock_client_device_id: MagicMock,
) -> None:
    """Test that we can handle invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_client_device_id.return_value = "TEST-UUID-1"
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass, "auth-login-failure.json"
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}

    mock_client_device_id.return_value = "TEST-UUID-2"
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass, "auth-login.json"
    )

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result3
    assert result3["type"] == "create_entry"
    assert result3["data"] == {
        CONF_CLIENT_DEVICE_ID: "TEST-UUID-1",
        CONF_URL: TEST_URL,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
