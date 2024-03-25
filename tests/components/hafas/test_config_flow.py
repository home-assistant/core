"""Test the HaFAS config flow."""

from homeassistant import config_entries
from homeassistant.components.hafas.const import (
    CONF_DESTINATION,
    CONF_ONLY_DIRECT,
    CONF_PROFILE,
    CONF_START,
    DOMAIN,
)
from homeassistant.const import CONF_OFFSET
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    TEST_OFFSET,
    TEST_ONLY_DIRECT,
    TEST_PROFILE,
    TEST_STATION1,
    TEST_STATION2,
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_USER,
        },
        data={
            CONF_PROFILE: TEST_PROFILE,
            CONF_START: TEST_STATION1,
            CONF_DESTINATION: TEST_STATION2,
            CONF_OFFSET: TEST_OFFSET,
            CONF_ONLY_DIRECT: TEST_ONLY_DIRECT,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "stations"

    station_result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input={
            CONF_START: TEST_STATION1,
            CONF_DESTINATION: TEST_STATION2,
        },
    )

    assert station_result["type"] == FlowResultType.CREATE_ENTRY
    assert station_result["title"] == f"{TEST_STATION1} to {TEST_STATION2}"
    assert station_result["data"] == {
        CONF_PROFILE: TEST_PROFILE,
        CONF_START: TEST_STATION1,
        CONF_DESTINATION: TEST_STATION2,
        CONF_OFFSET: TEST_OFFSET,
        CONF_ONLY_DIRECT: TEST_ONLY_DIRECT,
    }
