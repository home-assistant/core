"""Test the KAT Bulgaria config flow."""
from collections import namedtuple
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from kat_bulgaria.obligations import KatApiResponse, KatErrorType
import pytest

from homeassistant import config_entries
from homeassistant.components.kat_bulgaria.common import generate_entity_name
from homeassistant.components.kat_bulgaria.const import (
    CONF_DRIVING_LICENSE,
    CONF_PERSON_EGN,
    CONF_PERSON_NAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import KAT_API_VERIFY_CREDENTIALS


@pytest.fixture(autouse=True, name="mock_setup_entry")
def override_async_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.kat_bulgaria.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        KAT_API_VERIFY_CREDENTIALS,
        return_value=KatApiResponse(True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Nikola",
                CONF_PERSON_EGN: "0011223344",
                CONF_DRIVING_LICENSE: "123456879",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == generate_entity_name("Nikola")
    assert result2["data"] == {
        CONF_PERSON_NAME: "Nikola",
        CONF_PERSON_EGN: "0011223344",
        CONF_DRIVING_LICENSE: "123456879",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid user data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        KAT_API_VERIFY_CREDENTIALS,
        return_value=KatApiResponse(
            False, "Error message", KatErrorType.VALIDATION_ERROR
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Nikola",
                CONF_PERSON_EGN: "000",
                CONF_DRIVING_LICENSE: "123",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "invalid_config"


async def test_form_cannot_connect_website_down(hass: HomeAssistant) -> None:
    """Test the API is down."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        KAT_API_VERIFY_CREDENTIALS,
        return_value=KatApiResponse(
            False, "Error message", KatErrorType.API_UNAVAILABLE
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Nikola",
                CONF_PERSON_EGN: "0011223344",
                CONF_DRIVING_LICENSE: "123456879",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"


async def test_form_cannot_connect_timeout(hass: HomeAssistant) -> None:
    """Test the API timed out."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        KAT_API_VERIFY_CREDENTIALS,
        return_value=KatApiResponse(False, "Error message", KatErrorType.TIMEOUT),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Nikola",
                CONF_PERSON_EGN: "0011223344",
                CONF_DRIVING_LICENSE: "123456879",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"


async def test_form_unknown_error_type(hass: HomeAssistant) -> None:
    """Test unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        KAT_API_VERIFY_CREDENTIALS,
        return_value=KatApiResponse(False, "Error message", None),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Nikola",
                CONF_PERSON_EGN: "0011223344",
                CONF_DRIVING_LICENSE: "123456879",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "unknown"


async def test_form_already_configured_check_existing(hass: HomeAssistant) -> None:
    """Test adding an entity when it's already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.config_entries.ConfigFlow._async_current_entries",
        return_value=[
            namedtuple("Mock", ["data"])(
                data={
                    CONF_PERSON_NAME: "Nikola",
                    CONF_PERSON_EGN: "0011223344",
                    CONF_DRIVING_LICENSE: "123456879",
                }
            )
        ],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Nikola",
                CONF_PERSON_EGN: "0011223344",
                CONF_DRIVING_LICENSE: "123456879",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_already_configured_check_not_existing(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test adding an entity when another one was configured, no conflicts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        KAT_API_VERIFY_CREDENTIALS,
        return_value=KatApiResponse(True),
    ), patch(
        "homeassistant.config_entries.ConfigFlow._async_current_entries",
        return_value=[
            namedtuple("Mock", ["data"])(
                data={
                    CONF_PERSON_NAME: "Nikola",
                    CONF_PERSON_EGN: "9988776655",
                    CONF_DRIVING_LICENSE: "987654321",
                }
            )
        ],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Nikola",
                CONF_PERSON_EGN: "0011223344",
                CONF_DRIVING_LICENSE: "123456879",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == generate_entity_name("Nikola")
        assert result2["data"] == {
            CONF_PERSON_NAME: "Nikola",
            CONF_PERSON_EGN: "0011223344",
            CONF_DRIVING_LICENSE: "123456879",
        }
        assert len(mock_setup_entry.mock_calls) == 1
