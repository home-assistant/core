"""Test the Hikvision config flow."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    TEST_DEVICE_ID,
    TEST_DEVICE_NAME,
    TEST_HOST,
    TEST_PASSWORD,
    TEST_PORT,
    TEST_USERNAME,
)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form(hass: HomeAssistant, mock_hikcamera: MagicMock) -> None:
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
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["result"].unique_id == TEST_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
    }

    # Certificate verification defaults to on; it is unused over plain HTTP
    mock_hikcamera.assert_called_once_with(
        f"http://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_cannot_connect(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test we handle cannot connect error and can recover."""
    mock_hikcamera.return_value.get_id = None

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
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover from error
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_exception(hass: HomeAssistant, mock_hikcamera: MagicMock) -> None:
    """Test we handle exception during connection and can recover."""
    mock_hikcamera.side_effect = requests.exceptions.RequestException(
        "Connection failed"
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
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover from error
    mock_hikcamera.side_effect = None
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID
    mock_hikcamera.return_value.get_name = TEST_DEVICE_NAME

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_unknown_exception(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test we handle unknown exception during connection and can recover."""
    mock_hikcamera.side_effect = Exception("Unexpected error")

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
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover from error
    mock_hikcamera.side_effect = None
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID
    mock_hikcamera.return_value.get_name = TEST_DEVICE_NAME

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_already_configured(
    hass: HomeAssistant, mock_hikcamera: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle already configured devices."""
    mock_config_entry.add_to_hass(hass)

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
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("form", "verify_ssl"),
    [
        pytest.param({}, True, id="verified_by_default"),
        pytest.param({CONF_VERIFY_SSL: True}, True, id="verified"),
        pytest.param({CONF_VERIFY_SSL: False}, False, id="unverified"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_with_ssl(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    form: dict[str, bool],
    verify_ssl: bool,
) -> None:
    """Test the user flow passes HTTPS and the certificate choice to HikCamera."""
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
            CONF_SSL: True,
            **form,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SSL] is True
    assert result["data"][CONF_VERIFY_SSL] is verify_ssl
    assert result["result"].unique_id == TEST_DEVICE_ID
    mock_hikcamera.assert_called_once_with(
        f"https://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, verify_ssl
    )
