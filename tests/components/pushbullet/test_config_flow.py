"""Test pushbullet config flow."""

from unittest.mock import MagicMock, patch

from pushbullet import InvalidKeyError, PushbulletError
import pytest

from homeassistant import config_entries
from homeassistant.components.pushbullet.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG

from tests.common import MockConfigEntry

USER_INPUT = {CONF_API_KEY: "MYAPIKEY"}


@pytest.fixture(autouse=True)
def pushbullet_setup_fixture():
    """Patch pushbullet setup entry."""
    with patch(
        "homeassistant.components.pushbullet.async_setup_entry", return_value=True
    ):
        yield


async def test_flow_user(hass: HomeAssistant, requests_mock_fixture) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Some name"
    assert result["data"] == {CONF_NAME: "Some name", CONF_API_KEY: "MYAPIKEY"}
    assert result["result"].unique_id == "ujpah72o0"


async def test_flow_user_name_falls_back_to_email(hass: HomeAssistant) -> None:
    """Test the email is used when the account has no name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    with patch(
        "homeassistant.components.pushbullet.config_flow.PushBullet",
        return_value=MagicMock(
            user_info={"iden": "ujpah72o0", "name": "", "email": "example@email.com"}
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "example@email.com"
    assert result["data"] == {
        CONF_NAME: "example@email.com",
        CONF_API_KEY: "MYAPIKEY",
    }
    assert result["result"].unique_id == "ujpah72o0"


async def test_flow_user_already_configured(
    hass: HomeAssistant, requests_mock_fixture
) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="ujpah72o0",
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_invalid_key(hass: HomeAssistant) -> None:
    """Test user initialized flow with invalid api key."""

    with patch(
        "homeassistant.components.pushbullet.config_flow.PushBullet",
        side_effect=InvalidKeyError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_conn_error(hass: HomeAssistant) -> None:
    """Test user initialized flow with conn error."""

    with patch(
        "homeassistant.components.pushbullet.config_flow.PushBullet",
        side_effect=PushbulletError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
