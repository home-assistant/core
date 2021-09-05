"""Test the Discovergy config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

from pydiscovergy.error import HTTPError, InvalidLogin
from pydiscovergy.models import AccessToken, ConsumerToken

from homeassistant import setup
from homeassistant.components.discovergy.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.discovergy.const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_SECRET,
    CONF_CONSUMER_KEY,
    CONF_CONSUMER_SECRET,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


def get_discovergy_mock() -> MagicMock:
    """Return a MagicMock Discovergy instance for testing."""
    discovergy_mock = MagicMock()
    type(discovergy_mock).login = AsyncMock(
        return_value=(
            AccessToken("rq-test-token", "rq-test-token-secret"),
            ConsumerToken("test-key", "test-secret"),
        )
    )
    type(discovergy_mock).get_meters = AsyncMock(return_value=[])
    return discovergy_mock


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch("pydiscovergy.Discovergy", return_value=get_discovergy_mock(),), patch(
        "homeassistant.components.discovergy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "test@example.com"
    assert result2["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
        CONF_ACCESS_TOKEN: "rq-test-token",
        CONF_ACCESS_TOKEN_SECRET: "rq-test-token-secret",
        CONF_CONSUMER_KEY: "test-key",
        CONF_CONSUMER_SECRET: "test-secret",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "pydiscovergy.Discovergy.login",
        side_effect=InvalidLogin,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pydiscovergy.Discovergy.login", side_effect=HTTPError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pydiscovergy.Discovergy.login", side_effect=Exception):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_automatic_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the automatic rauth flow."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "pydiscovergy.Discovergy", return_value=get_discovergy_mock()
    ) as mock_discovergy, patch(
        "homeassistant.components.discovergy.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "unique_id": mock_config_entry.unique_id,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )
        await hass.async_block_till_done()

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "reauth_successful"

    assert mock_discovergy.call_count == 1
    assert mock_setup_entry.call_count == 1


async def test_automatic_reauth_flow_missing_entry(hass: HomeAssistant) -> None:
    """Test the automatic rauth flow if it is missing the config entry."""
    with patch("pydiscovergy.Discovergy", return_value=get_discovergy_mock()), patch(
        "homeassistant.components.discovergy.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "unique_id": "abc123xyz",
                "entry_id": "abc123",
            },
            data={},
        )
        await hass.async_block_till_done()

    assert result.get("type") == RESULT_TYPE_FORM


async def test_automatic_reauth_flow_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the automatic reauth flow if a connection error is raised."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.discovergy.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "unique_id": mock_config_entry.unique_id,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == "reauth_confirm"
    assert "flow_id" in result


async def test_automatic_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the automatic reauth flow if a invalid auth error is raised."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.discovergy.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "unique_id": mock_config_entry.unique_id,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == "reauth_confirm"
    assert "flow_id" in result


async def test_manual_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the manual reauth flow."""
    mock_config_entry.add_to_hass(hass)

    # check automatic re-auth flow with InvalidLogin exception raised
    with patch("pydiscovergy.Discovergy.login", side_effec=InvalidLogin):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "unique_id": mock_config_entry.unique_id,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )
        await hass.async_block_till_done()

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == "reauth_confirm"
    assert "flow_id" in result

    # now check reauth_confirm flow with supplied password
    with patch("pydiscovergy.Discovergy", return_value=get_discovergy_mock()), patch(
        "homeassistant.components.discovergy.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test-password"},
        )
        await hass.async_block_till_done()

    assert result2.get("type") == RESULT_TYPE_ABORT
    assert result2.get("reason") == "reauth_successful"
