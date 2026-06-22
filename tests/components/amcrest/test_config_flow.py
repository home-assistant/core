"""Test the Amcrest config flow."""

from unittest.mock import MagicMock

from amcrest import AmcrestError, LoginError
import pytest

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from .conftest import (
    TEST_HOST,
    TEST_PASSWORD,
    TEST_PORT,
    TEST_SERIAL,
    TEST_USERNAME,
    mock_async_property,
)

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_amcrest_api: MagicMock,
) -> None:
    """Test we get the form and can create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Amcrest {TEST_SERIAL}"
    assert result["result"].unique_id == TEST_SERIAL
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }


async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_amcrest_api: MagicMock,
) -> None:
    """Test we handle invalid auth."""
    mock_async_property(
        mock_amcrest_api.return_value,
        "async_current_time",
        side_effect=LoginError,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_async_property(
        mock_amcrest_api.return_value, "async_current_time", return_value=None
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Amcrest {TEST_SERIAL}"


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_amcrest_api: MagicMock,
) -> None:
    """Test we handle cannot connect error."""
    mock_async_property(
        mock_amcrest_api.return_value,
        "async_current_time",
        side_effect=AmcrestError,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_port(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_amcrest_api: MagicMock,
) -> None:
    """Test we handle invalid port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
                CONF_PORT: 70000,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )


async def test_form_unique_id_already_exists(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_amcrest_api: MagicMock,
) -> None:
    """Test we handle duplicate unique id."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 80,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
        unique_id=TEST_SERIAL,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_no_serial_number(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_amcrest_api: MagicMock,
) -> None:
    """Test we handle missing serial number."""
    mock_async_property(
        mock_amcrest_api.return_value, "async_serial_number", return_value=None
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_serial_number"}

    mock_async_property(
        mock_amcrest_api.return_value, "async_serial_number", return_value=TEST_SERIAL
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Amcrest {TEST_SERIAL}"


async def test_form_unknown(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_amcrest_api: MagicMock,
) -> None:
    """Test we handle unexpected errors."""
    mock_async_property(
        mock_amcrest_api.return_value,
        "async_current_time",
        side_effect=RuntimeError,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
