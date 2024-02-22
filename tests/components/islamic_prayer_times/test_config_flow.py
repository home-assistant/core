"""Tests for Islamic Prayer Times config flow."""
from unittest.mock import patch

from prayer_times_calculator import InvalidResponseError
import pytest
from requests.exceptions import ConnectionError as ConnError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import islamic_prayer_times
from homeassistant.components.islamic_prayer_times.const import (
    CONF_CALC_METHOD,
    CONF_LAT_ADJ_METHOD,
    CONF_MIDNIGHT_MODE,
    CONF_SCHOOL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from . import MOCK_CONFIG, MOCK_USER_INPUT

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_flow_works(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        islamic_prayer_times.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.islamic_prayer_times.config_flow.async_validate_location",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (InvalidResponseError, "invalid_location"),
        (ConnError, "conn_error"),
    ],
)
async def test_flow_error(
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    """Test flow errors."""
    result = await hass.config_entries.flow.async_init(
        islamic_prayer_times.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.islamic_prayer_times.config_flow.PrayerTimesCalculator.fetch_prayer_times",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == error


async def test_options(hass: HomeAssistant) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Islamic Prayer Times",
        data=MOCK_CONFIG,
        options={CONF_CALC_METHOD: "isna"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CALC_METHOD: "makkah",
            CONF_LAT_ADJ_METHOD: "one_seventh",
            CONF_SCHOOL: "hanafi",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CALC_METHOD] == "makkah"
    assert result["data"][CONF_LAT_ADJ_METHOD] == "one_seventh"
    assert result["data"][CONF_MIDNIGHT_MODE] == "standard"
    assert result["data"][CONF_SCHOOL] == "hanafi"


async def test_integration_already_configured(hass: HomeAssistant) -> None:
    """Test integration is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options={}, unique_id="12.34-23.45"
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        islamic_prayer_times.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
