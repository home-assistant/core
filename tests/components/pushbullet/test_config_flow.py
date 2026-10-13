"""Test pushbullet config flow."""

from unittest.mock import MagicMock, patch

from pushbullet import InvalidKeyError, PushbulletError
import pytest

from homeassistant import config_entries
from homeassistant.components.pushbullet.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


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
        user_input=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "pushbullet"
    assert result["data"] == MOCK_CONFIG
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
        user_input=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_name_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="MYAPIKEY",
    )

    entry.add_to_hass(hass)

    new_config = MOCK_CONFIG.copy()
    new_config[CONF_API_KEY] = "NEWKEY"

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
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
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
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth updates the API key."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id="ujpah72o0")
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "NEWKEY"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == MOCK_CONFIG | {CONF_API_KEY: "NEWKEY"}


@pytest.mark.parametrize(
    ("side_effect", "errors"),
    [
        pytest.param(
            InvalidKeyError, {CONF_API_KEY: "invalid_api_key"}, id="invalid_api_key"
        ),
        pytest.param(PushbulletError, {"base": "cannot_connect"}, id="cannot_connect"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, side_effect: type[Exception], errors: dict[str, str]
) -> None:
    """Test reauth handles errors and can recover."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id="ujpah72o0")
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.pushbullet.config_flow.PushBullet",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "NEWKEY"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "NEWKEY"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "NEWKEY"


async def test_reauth_wrong_account(hass: HomeAssistant) -> None:
    """Test reauth aborts when the API key belongs to another account."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id="ujpah72o0")
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.pushbullet.config_flow.PushBullet",
        return_value=MagicMock(user_info={"iden": "other_account"}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "OTHERKEY"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data == MOCK_CONFIG
