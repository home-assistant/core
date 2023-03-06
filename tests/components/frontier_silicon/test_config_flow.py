"""Test the Frontier Silicon config flow."""
from unittest.mock import patch

from afsapi import ConnectionError, InvalidPinException
import pytest

from homeassistant import config_entries
from homeassistant.components.frontier_silicon.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_import_success(hass: HomeAssistant) -> None:
    """Test successful import."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 80,
            CONF_PIN: "1234",
            CONF_NAME: "Test name",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("webfsapi_endpoint_error", "result_reason"),
    [
        (ConnectionError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_import_webfsapi_endpoint_failures(
    hass: HomeAssistant, webfsapi_endpoint_error: Exception, result_reason: str
) -> None:
    """Test various failure of get_webfsapi_endpoint."""
    with patch(
        "afsapi.AFSAPI.get_webfsapi_endpoint",
        side_effect=webfsapi_endpoint_error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_PIN: "1234",
                CONF_NAME: "Test name",
            },
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == result_reason


@pytest.mark.parametrize(
    ("radio_id_error", "result_reason"),
    [
        (ConnectionError, "cannot_connect"),
        (InvalidPinException, "invalid_auth"),
        (ValueError, "unknown"),
    ],
)
async def test_import_radio_id_failures(
    hass: HomeAssistant, radio_id_error: Exception, result_reason: str
) -> None:
    """Test various failure of get_radio_id."""
    with patch(
        "afsapi.AFSAPI.get_radio_id",
        side_effect=radio_id_error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_PIN: "1234",
                CONF_NAME: "Test name",
            },
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == result_reason


async def test_import_already_exists(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test import of device which already exists."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 80,
            CONF_PIN: "1234",
            CONF_NAME: "Test name",
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_default_pin(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test manual device add with default pin."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Name of the device"
    assert result2["data"] == {
        "webfsapi_url": "http://1.1.1.1:80/webfsapi",
        "pin": "1234",
    }
    mock_setup_entry.assert_called_once()


async def test_form_nondefault_pin(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "afsapi.AFSAPI.get_friendly_name",
        side_effect=InvalidPinException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] is None

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_PIN: "4321"},
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Name of the device"
    assert result3["data"] == {
        "webfsapi_url": "http://1.1.1.1:80/webfsapi",
        "pin": "4321",
    }
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("friendly_name_error", "result_error"),
    [
        (ConnectionError, "cannot_connect"),
        (InvalidPinException, "invalid_auth"),
        (ValueError, "unknown"),
    ],
)
async def test_form_nondefault_pin_invalid(
    hass: HomeAssistant, friendly_name_error: Exception, result_error: str
) -> None:
    """Test we get the proper errors when trying to validate an user-provided PIN."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "afsapi.AFSAPI.get_friendly_name",
        side_effect=InvalidPinException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] is None

    with patch(
        "afsapi.AFSAPI.get_friendly_name",
        side_effect=friendly_name_error,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_PIN: "4321"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": result_error}


@pytest.mark.parametrize(
    ("webfsapi_endpoint_error", "result_error"),
    [
        (ConnectionError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_invalid_device_url(
    hass: HomeAssistant, webfsapi_endpoint_error: Exception, result_error: str
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "afsapi.AFSAPI.get_webfsapi_endpoint",
        side_effect=webfsapi_endpoint_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": result_error}
