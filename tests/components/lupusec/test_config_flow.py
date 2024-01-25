""""Unit tests for the Lupusec config flow."""

from unittest.mock import patch

from lupupy import LupusecException
import pytest

from homeassistant import config_entries
from homeassistant.components.lupusec.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
    FlowResultType,
)

from tests.common import MockConfigEntry

MOCK_DATA_STEP = {
    CONF_HOST: "test-host.lan",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock StreamLabs config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test-host.lan",
        data=MOCK_DATA_STEP,
    )


async def test_form_valid_input(hass: HomeAssistant) -> None:
    """Test handling valid user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lupusec.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "lupupy.Lupusec.__init__",
        return_value=None,
    ) as mock_initialize_lupusec:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_DATA_STEP,
        )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == MOCK_DATA_STEP[CONF_HOST]
    assert result2["data"] == MOCK_DATA_STEP
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_initialize_lupusec.mock_calls) == 1


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test handling invalid host input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "invalid_host",
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_lupusec_exception(hass: HomeAssistant) -> None:
    """Test handling valid user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "lupupy.Lupusec.__init__",
        side_effect=LupusecException("Test Lupusec Exception"),
    ) as mock_step_user:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_DATA_STEP,
        )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    assert len(mock_step_user.mock_calls) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (LupusecException("Test lupusec exception"), "cannot_connect"),
        (Exception("Test unknown exception"), "unknown"),
    ],
)
async def test_flow_user_init_data_error_and_recover(
    hass: HomeAssistant, raise_error, text_error
) -> None:
    """Test handling valid user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "lupupy.Lupusec.__init__",
        side_effect=raise_error,
    ) as mock_step_user:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_DATA_STEP,
        )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": text_error}

    assert len(mock_step_user.mock_calls) == 1
