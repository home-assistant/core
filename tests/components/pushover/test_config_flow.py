"""Test pushbullet config flow."""

from unittest.mock import MagicMock, patch

from pushover_complete import BadAPIRequestError
import pytest

from homeassistant import config_entries
from homeassistant.components.pushover.const import CONF_USER_KEY, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_pushover():
    """Mock pushover."""
    with patch(
        "pushover_complete.PushoverAPI._generic_post", return_value={}
    ) as mock_generic_post:
        yield mock_generic_post


@pytest.fixture(autouse=True)
def pushover_setup_fixture():
    """Patch pushover setup entry."""
    with patch(
        "homeassistant.components.pushover.async_setup_entry", return_value=True
    ):
        yield


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Pushover"
    assert result["data"] == MOCK_CONFIG


async def test_flow_user_key_api_key_exists(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate user key / api key pair."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_name_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="MYUSERKEY",
    )

    entry.add_to_hass(hass)

    new_config = MOCK_CONFIG.copy()
    new_config[CONF_USER_KEY] = "NEUSERWKEY"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=new_config,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_invalid_user_key(
    hass: HomeAssistant, mock_pushover: MagicMock
) -> None:
    """Test user initialized flow with wrong user key."""

    mock_pushover.side_effect = BadAPIRequestError("400: user key is invalid")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_USER_KEY: "invalid_user_key"}


async def test_flow_invalid_api_key(
    hass: HomeAssistant, mock_pushover: MagicMock
) -> None:
    """Test user initialized flow with wrong api key."""

    mock_pushover.side_effect = BadAPIRequestError("400: application token is invalid")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_flow_conn_err(hass: HomeAssistant, mock_pushover: MagicMock) -> None:
    """Test user initialized flow with conn error."""

    mock_pushover.side_effect = BadAPIRequestError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "NEWAPIKEY",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauth_failed(hass: HomeAssistant, mock_pushover: MagicMock) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_pushover.side_effect = BadAPIRequestError("400: application token is invalid")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "WRONGAPIKEY",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {
        CONF_API_KEY: "invalid_api_key",
    }


async def test_reauth_with_existing_config(hass: HomeAssistant) -> None:
    """Test reauth fails if the api key entered exists in another entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    second_entry = MOCK_CONFIG.copy()
    second_entry[CONF_API_KEY] = "MYAPIKEY2"

    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data=second_entry,
    )
    entry2.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "MYAPIKEY2",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
