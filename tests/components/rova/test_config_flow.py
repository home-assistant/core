"""Tests for the Rova config flow."""

from unittest.mock import MagicMock

import pytest
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.components.rova.const import (
    CONF_HOUSE_NUMBER,
    CONF_HOUSE_NUMBER_SUFFIX,
    CONF_ZIP_CODE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

ZIP_CODE = "7991AD"
HOUSE_NUMBER = "10"
HOUSE_NUMBER_SUFFIX = "a"


async def test_user(hass: HomeAssistant, mock_rova: MagicMock) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    # test with all information provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY

    data = result.get("data")
    assert data
    assert data[CONF_ZIP_CODE] == ZIP_CODE
    assert data[CONF_HOUSE_NUMBER] == HOUSE_NUMBER
    assert data[CONF_HOUSE_NUMBER_SUFFIX] == HOUSE_NUMBER_SUFFIX


async def test_error_if_not_rova_area(
    hass: HomeAssistant, mock_rova: MagicMock
) -> None:
    """Test we raise errors if rova does not collect at the given address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # test with area where rova does not collect
    mock_rova.return_value.is_rova_area.return_value = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_rova_area"}

    # now reset the return value and test if we can recover
    mock_rova.return_value.is_rova_area.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{ZIP_CODE} {HOUSE_NUMBER} {HOUSE_NUMBER_SUFFIX}"
    assert result["data"] == {
        CONF_ZIP_CODE: ZIP_CODE,
        CONF_HOUSE_NUMBER: HOUSE_NUMBER,
        CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
    }


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if rova is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{ZIP_CODE}{HOUSE_NUMBER}{HOUSE_NUMBER_SUFFIX}",
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ConnectTimeout(), "cannot_connect"),
        (HTTPError(), "cannot_connect"),
    ],
)
async def test_abort_if_api_throws_exception(
    hass: HomeAssistant, exception: Exception, error: str, mock_rova: MagicMock
) -> None:
    """Test different exceptions for the Rova entity."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # test with exception
    mock_rova.return_value.is_rova_area.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": error}

    # now reset the side effect to see if we can recover
    mock_rova.return_value.is_rova_area.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{ZIP_CODE} {HOUSE_NUMBER} {HOUSE_NUMBER_SUFFIX}"
    assert result["data"] == {
        CONF_ZIP_CODE: ZIP_CODE,
        CONF_HOUSE_NUMBER: HOUSE_NUMBER,
        CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
    }


async def test_import(hass: HomeAssistant, mock_rova: MagicMock) -> None:
    """Test import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{ZIP_CODE} {HOUSE_NUMBER} {HOUSE_NUMBER_SUFFIX}"
    assert result["data"] == {
        CONF_ZIP_CODE: ZIP_CODE,
        CONF_HOUSE_NUMBER: HOUSE_NUMBER,
        CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
    }


async def test_import_already_configured(
    hass: HomeAssistant, mock_rova: MagicMock
) -> None:
    """Test we abort import flow when entry is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{ZIP_CODE}{HOUSE_NUMBER}{HOUSE_NUMBER_SUFFIX}",
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_if_not_rova_area(
    hass: HomeAssistant, mock_rova: MagicMock
) -> None:
    """Test we abort if rova does not collect at the given address."""

    # test with area where rova does not collect
    mock_rova.return_value.is_rova_area.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "invalid_rova_area"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ConnectTimeout(), "cannot_connect"),
        (HTTPError(), "cannot_connect"),
    ],
)
async def test_import_connection_errors(
    hass: HomeAssistant, exception: Exception, error: str, mock_rova: MagicMock
) -> None:
    """Test import connection errors flow."""

    # test with HTTPError
    mock_rova.return_value.is_rova_area.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == error
