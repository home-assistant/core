"""Test Unmanic config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.unmanic.const import DOMAIN, NAME

from .common import mock_unmanic_version_api_response
from .const import MOCK_CONFIG


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "homeassistant.components.unmanic.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_successful_config_flow(hass):
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert len(result["errors"]) == 0

    with patch(
        "unmanic_api.Unmanic.get_version",
        return_value=mock_unmanic_version_api_response(),
    ), patch(
        "homeassistant.components.unmanic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_CONFIG,
        )
        await hass.async_block_till_done()

    print(result2)
    assert result2["title"] == f"{NAME} (127.0.0.2)"
    assert result2["data"] == MOCK_CONFIG
    assert result2["data"]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_failed_config_flow(hass, error_on_get_data):
    """Test a failed config flow due to credential validation failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}
