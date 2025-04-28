"""Test the Kem config flow."""

from unittest.mock import AsyncMock, patch

from aiokem import AuthenticationCredentialsError
import pytest

from homeassistant import config_entries
from homeassistant.components.kem.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_authenticate")
async def platform_sensor_fixture():
    """Patch KEM to only load Sensor platform."""
    with patch("homeassistant.components.kem.data.AioKem.authenticate") as mock_auth:
        yield mock_auth


async def test_configure_entry(
    hass: HomeAssistant, mock_authenticate: AsyncMock
) -> None:
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
                "email": "TEST-email",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-email"
    assert result["data"] == {
        "email": "TEST-email",
        "password": "test-password",
    }
    assert mock_setup_entry.call_count == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_authenticate: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_authenticate.side_effect = AuthenticationCredentialsError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "test-email",
            "password": "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_authenticate: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_authenticate.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "test-email",
            "password": "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(
    hass: HomeAssistant, mock_authenticate: AsyncMock
) -> None:
    """Test we handle unknown exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_authenticate.side_effect = Exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "test-email",
            "password": "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "TEST-email",
            "password": "test-password",
        },
        unique_id="test-email",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("homeassistant.components.kem.data.AioKem.authenticate"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "test-email",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "any",
            CONF_PASSWORD: "old",
        },
    )
    config_entry.add_to_hass(hass)
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    flow = flows[0]

    with patch(
        "homeassistant.components.kem.data.AioKem.authenticate",
        side_effect=AuthenticationCredentialsError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"password": "invalid_auth"}

    with (
        patch("homeassistant.components.kem.data.AioKem.authenticate"),
        patch(
            "homeassistant.components.kem.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PASSWORD] == "test-password"
    assert mock_setup_entry.call_count == 1
