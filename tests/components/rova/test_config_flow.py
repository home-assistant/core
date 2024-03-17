"""Tests for the Rova config flow."""
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant import data_entry_flow
from homeassistant.components.rova.const import (
    CONF_HOUSE_NUMBER,
    CONF_HOUSE_NUMBER_SUFFIX,
    CONF_ZIP_CODE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ZIP_CODE = "7991AD"
HOUSE_NUMBER = "10"
HOUSE_NUMBER_SUFFIX = "a"


@pytest.fixture(name="test_api")
def mock_controller():
    """Mock a successful Rova API."""
    api = Mock()
    api.is_rova_area.return_value = True

    with patch("rova.rova.Rova", return_value=api):
        yield api


async def test_user(hass: HomeAssistant, test_api: Mock) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
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
    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY

    data = result.get("data")
    assert data
    assert data[CONF_ZIP_CODE] == ZIP_CODE
    assert data[CONF_HOUSE_NUMBER] == HOUSE_NUMBER
    assert data[CONF_HOUSE_NUMBER_SUFFIX] == HOUSE_NUMBER_SUFFIX


async def test_abort_if_not_rova_area(hass: HomeAssistant, test_api: Mock) -> None:
    """Test we abort if rova does not collect at the given address."""

    # test with area where rova does not collect
    test_api.is_rova_area.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_rova_area"}


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if rova is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
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
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_asserts(hass: HomeAssistant, test_api: Mock) -> None:
    """Test the _site_in_configuration_exists method."""

    # test with ConnectionTimeout
    test_api.is_rova_area.side_effect = ConnectTimeout()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}

    # test with HTTPError
    test_api.is_rova_area.side_effect = HTTPError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_import(hass: HomeAssistant, test_api: Mock) -> None:
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

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{ZIP_CODE} {HOUSE_NUMBER} {HOUSE_NUMBER_SUFFIX}".strip()
    assert result["data"] == {
        CONF_ZIP_CODE: ZIP_CODE,
        CONF_HOUSE_NUMBER: HOUSE_NUMBER,
        CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
    }


async def test_import_if_not_rova_area(hass: HomeAssistant, test_api: Mock) -> None:
    """Test we abort if rova does not collect at the given address."""

    # test with area where rova does not collect
    test_api.is_rova_area.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )

    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "invalid_rova_area"


async def test_import_connection_errors(hass: HomeAssistant, test_api: Mock) -> None:
    """Test import connection errors flow."""

    # test with HTTPError
    test_api.is_rova_area.side_effect = HTTPError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )

    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"

    # test with ConnectTimeout
    test_api.is_rova_area.side_effect = ConnectTimeout()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_ZIP_CODE: ZIP_CODE,
            CONF_HOUSE_NUMBER: HOUSE_NUMBER,
            CONF_HOUSE_NUMBER_SUFFIX: HOUSE_NUMBER_SUFFIX,
        },
    )

    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"
