"""Test the binary sensors."""

from unittest.mock import patch

from kat_bulgaria.obligations import KatApiResponse, KatErrorType

from homeassistant import config_entries
from homeassistant.components.kat_bulgaria.const import (
    ATTR_LAST_UPDATED,
    CONF_DRIVING_LICENSE,
    CONF_PERSON_EGN,
    CONF_PERSON_NAME,
    DOMAIN,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .const import KAT_API_CHECK_OBLIGATIONS, KAT_API_VERIFY_CREDENTIALS


async def test_sensor_update_success(hass: HomeAssistant) -> None:
    """Test successful sensor add."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        KAT_API_VERIFY_CREDENTIALS,
        return_value=KatApiResponse(True),
    ), patch(
        KAT_API_CHECK_OBLIGATIONS,
        return_value=KatApiResponse(True),
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Nikola",
                CONF_PERSON_EGN: "0011223344",
                CONF_DRIVING_LICENSE: "123456879",
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.globi_nikola")
    assert state
    assert state.state == "on"
    assert ATTR_LAST_UPDATED in state.attributes


async def test_sensor_update_failed(hass: HomeAssistant) -> None:
    """Test sensor is not updated if API is down."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        KAT_API_VERIFY_CREDENTIALS,
        return_value=KatApiResponse(True),
    ), patch(
        KAT_API_CHECK_OBLIGATIONS,
        return_value=KatApiResponse(
            False, "Error message", KatErrorType.API_UNAVAILABLE
        ),
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Nikola",
                CONF_PERSON_EGN: "0011223344",
                CONF_DRIVING_LICENSE: "123456879",
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.globi_nikola")
    assert state
    assert state.state == STATE_UNKNOWN
    assert ATTR_LAST_UPDATED not in state.attributes
