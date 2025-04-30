"""Test the Kem config flow."""

from unittest.mock import AsyncMock, patch

from aiokem import AuthenticationCredentialsError
import pytest

from homeassistant import config_entries
from homeassistant.components.kem.const import DOMAIN
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_EMAIL, TEST_PASSWORD, TEST_SUBJECT


async def test_configure_entry(hass: HomeAssistant, mock_kem: AsyncMock) -> None:
    """Test we can configure the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.kem.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL.lower()
    assert result["data"] == {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    }
    assert result["result"].unique_id == TEST_SUBJECT
    assert mock_setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("error", "conf_error"),
    [
        (AuthenticationCredentialsError, {CONF_PASSWORD: "invalid_auth"}),
        (TimeoutError, {"base": "cannot_connect"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_configure_entry_exceptions(
    hass: HomeAssistant,
    mock_kem: AsyncMock,
    error: Exception,
    conf_error: dict[str, str],
) -> None:
    """Test we handle a variety of exceptions and recover by adding new entry."""
    with patch(
        "homeassistant.components.kem.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        # First try to authenticate and get an error
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        mock_kem.authenticate.side_effect = error
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == conf_error
        assert mock_setup_entry.call_count == 0

        # Now try to authenticate again and succeed
        # This should create a new entry
        mock_kem.authenticate.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == TEST_EMAIL.lower()
        assert result["data"] == {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        }
        assert result["result"].unique_id == TEST_SUBJECT
        assert mock_setup_entry.call_count == 1


async def test_already_configured(
    hass: HomeAssistant, kem_config_entry, mock_kem: AsyncMock
) -> None:
    """Test if entry is already configured."""
    kem_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant, kem_config_entry, mock_kem: AsyncMock
) -> None:
    """Test reauth flow."""
    kem_config_entry.add_to_hass(hass)
    kem_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    flow = flows[0]

    with patch(
        "homeassistant.components.kem.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                CONF_PASSWORD: TEST_PASSWORD + "new",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert kem_config_entry.data[CONF_PASSWORD] == TEST_PASSWORD + "new"
    assert mock_setup_entry.call_count == 1


async def test_reauth_exception(
    hass: HomeAssistant, kem_config_entry, mock_kem: AsyncMock
) -> None:
    """Test reauth flow."""
    kem_config_entry.add_to_hass(hass)
    kem_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    flow = flows[0]

    mock_kem.authenticate.side_effect = AuthenticationCredentialsError
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"password": "invalid_auth"}
