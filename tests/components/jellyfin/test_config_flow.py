"""Test the jellyfin config flow."""

from unittest.mock import MagicMock

import pytest
from voluptuous.error import Invalid

from homeassistant import config_entries
from homeassistant.components.jellyfin.const import (
    CONF_AUDIO_CODEC,
    CONF_CLIENT_DEVICE_ID,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import async_load_json_fixture
from .const import REAUTH_INPUT, TEST_PASSWORD, TEST_URL, TEST_USERNAME, USER_INPUT

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_abort_if_existing_entry(hass: HomeAssistant) -> None:
    """Check flow abort when an entry already exist."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
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

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
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
    """Test configuration with an unreachable server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_client.auth.connect_to_address.return_value = await async_load_json_fixture(
        hass, "auth-connect-address-failure.json"
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    assert len(mock_client.auth.connect_to_address.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
    mock_client_device_id: MagicMock,
) -> None:
    """Test configuration with invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass, "auth-login-failure.json"
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    assert len(mock_client.auth.connect_to_address.mock_calls) == 1
    assert len(mock_client.auth.login.mock_calls) == 1


async def test_form_exception(
    hass: HomeAssistant, mock_jellyfin: MagicMock, mock_client: MagicMock
) -> None:
    """Test configuration with an unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_client.auth.connect_to_address.side_effect = Exception("UnknownException")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    assert len(mock_client.auth.connect_to_address.mock_calls) == 1


async def test_form_persists_device_id_on_error(
    hass: HomeAssistant,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
    mock_client_device_id: MagicMock,
) -> None:
    """Test persisting the device id on error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_client_device_id.return_value = "TEST-UUID-1"
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass, "auth-login-failure.json"
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    mock_client_device_id.return_value = "TEST-UUID-2"
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass, "auth-login.json"
    )

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input=USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result3
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        CONF_CLIENT_DEVICE_ID: "TEST-UUID-1",
        CONF_URL: TEST_URL,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }


async def test_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test a reauth flow."""
    # Force a reauth
    mock_client.auth.connect_to_address.return_value = await async_load_json_fixture(
        hass,
        "auth-connect-address.json",
    )
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass,
        "auth-login-failure.json",
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    # Complete the reauth
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass,
        "auth-login.json",
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=REAUTH_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauth_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test an unreachable server during a reauth flow."""
    # Force a reauth
    mock_client.auth.connect_to_address.return_value = await async_load_json_fixture(
        hass,
        "auth-connect-address.json",
    )
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass,
        "auth-login-failure.json",
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    # Perform reauth with unreachable server
    mock_client.auth.connect_to_address.return_value = await async_load_json_fixture(
        hass, "auth-connect-address-failure.json"
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=REAUTH_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    assert len(mock_client.auth.connect_to_address.mock_calls) == 1

    # Complete reauth with reachable server
    mock_client.auth.connect_to_address.return_value = await async_load_json_fixture(
        hass, "auth-connect-address.json"
    )
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass,
        "auth-login.json",
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=REAUTH_INPUT,
    )
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"


async def test_reauth_invalid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test invalid credentials during a reauth flow."""
    # Force a reauth
    mock_client.auth.connect_to_address.return_value = await async_load_json_fixture(
        hass,
        "auth-connect-address.json",
    )
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass,
        "auth-login-failure.json",
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    # Perform reauth with invalid credentials
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=REAUTH_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    assert len(mock_client.auth.connect_to_address.mock_calls) == 1
    assert len(mock_client.auth.login.mock_calls) == 1

    # Complete reauth with valid credentials
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass,
        "auth-login.json",
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=REAUTH_INPUT,
    )
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"


async def test_reauth_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test an unexpected exception during a reauth flow."""
    # Force a reauth
    mock_client.auth.connect_to_address.return_value = await async_load_json_fixture(
        hass,
        "auth-connect-address.json",
    )
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass,
        "auth-login-failure.json",
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    # Perform a reauth with an unknown exception
    mock_client.auth.connect_to_address.side_effect = Exception("UnknownException")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=REAUTH_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    assert len(mock_client.auth.connect_to_address.mock_calls) == 1

    # Complete the reauth without an exception
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass,
        "auth-login.json",
    )
    mock_client.auth.connect_to_address.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=REAUTH_INPUT,
    )
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test config flow options."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    assert config_entry.options == {}
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # Audio Codec
    # Default
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert CONF_AUDIO_CODEC not in config_entry.options

    # Bad
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    with pytest.raises(Invalid):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_AUDIO_CODEC: "ogg"}
        )


@pytest.mark.parametrize(
    "codec",
    [("aac"), ("wma"), ("vorbis"), ("mp3")],
)
async def test_setting_codec(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
    codec: str,
) -> None:
    """Test setting the audio_codec."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_AUDIO_CODEC: codec}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_AUDIO_CODEC] == codec
