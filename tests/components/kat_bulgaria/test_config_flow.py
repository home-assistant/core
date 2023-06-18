"""Test the KAT Bulgaria config flow."""
from collections import namedtuple
from unittest.mock import patch

from kat_bulgaria.obligations import KatApiResponse, KatErrorType

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

from .const import (
    EGN_SAMPLE,
    EGN_SAMPLE_TWO,
    KAT_API_VERIFY_CREDENTIALS,
    LICENSE_SAMPLE,
    LICENSE_SAMPLE_TWO,
)


async def test_form(hass: HomeAssistant) -> None:
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
                CONF_PERSON_EGN: EGN_SAMPLE,
                CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == generate_entity_name("Nikola")
    assert result2["data"] == {
        CONF_PERSON_NAME: "Nikola",
        CONF_PERSON_EGN: EGN_SAMPLE,
        CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
    }


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
                CONF_DRIVING_LICENSE: "999",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_config"


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
                CONF_PERSON_EGN: EGN_SAMPLE,
                CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


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
                CONF_PERSON_EGN: EGN_SAMPLE,
                CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


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
                CONF_PERSON_EGN: EGN_SAMPLE,
                CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "unknown"


async def test_form_already_configured_with_existing(hass: HomeAssistant) -> None:
    """Test adding an entity when it's already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.config_entries.ConfigFlow._async_current_entries",
        return_value=[
            namedtuple("Mock", ["data", "unique_id", "source"])(
                data={
                    CONF_PERSON_NAME: "Nikola",
                    CONF_PERSON_EGN: EGN_SAMPLE,
                    CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
                },
                unique_id=EGN_SAMPLE,
                source=config_entries.SOURCE_USER,
            ),
        ],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Nikola",
                CONF_PERSON_EGN: EGN_SAMPLE,
                CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_already_configured_without_existing(hass: HomeAssistant) -> None:
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
            namedtuple("Mock", ["data", "unique_id", "source"])(
                data={
                    CONF_PERSON_NAME: "Nikola",
                    CONF_PERSON_EGN: EGN_SAMPLE_TWO,
                    CONF_DRIVING_LICENSE: LICENSE_SAMPLE_TWO,
                },
                unique_id=EGN_SAMPLE_TWO,
                source=config_entries.SOURCE_USER,
            ),
        ],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Nikola",
                CONF_PERSON_EGN: EGN_SAMPLE,
                CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == generate_entity_name("Nikola")
        assert result2["data"] == {
            CONF_PERSON_NAME: "Nikola",
            CONF_PERSON_EGN: EGN_SAMPLE,
            CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
        }
