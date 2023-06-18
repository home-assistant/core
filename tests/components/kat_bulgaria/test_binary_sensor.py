"""Test the binary sensors."""

from unittest.mock import patch

from kat_bulgaria.obligations import KatApiResponse, KatErrorType

from homeassistant import config_entries
from homeassistant.components.kat_bulgaria.const import (
    CONF_DRIVING_LICENSE,
    CONF_PERSON_EGN,
    CONF_PERSON_NAME,
    DOMAIN,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .const import (
    EGN_SAMPLE,
    KAT_API_CHECK_OBLIGATIONS,
    KAT_API_VERIFY_CREDENTIALS,
    LICENSE_SAMPLE,
)

from tests.common import MockConfigEntry


async def test_sensor_update_success_with_obligations(hass: HomeAssistant) -> None:
    """Test successful sensor add."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PERSON_NAME: "Nikola",
            CONF_PERSON_EGN: EGN_SAMPLE,
            CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
        },
        unique_id=EGN_SAMPLE,
    )

    with patch(
        KAT_API_VERIFY_CREDENTIALS,
        return_value=KatApiResponse(True),
    ), patch(
        KAT_API_CHECK_OBLIGATIONS,
        return_value=KatApiResponse(True),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED

    state = hass.states.get("binary_sensor.globi_nikola")
    assert state
    assert state.state == "on"


async def test_sensor_update_success_without_obligations(hass: HomeAssistant) -> None:
    """Test successful sensor add."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PERSON_NAME: "Nikola",
            CONF_PERSON_EGN: EGN_SAMPLE,
            CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
        },
        unique_id=EGN_SAMPLE,
    )

    with patch(
        KAT_API_VERIFY_CREDENTIALS,
        return_value=KatApiResponse(True),
    ), patch(
        KAT_API_CHECK_OBLIGATIONS,
        return_value=KatApiResponse(False),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED

    state = hass.states.get("binary_sensor.globi_nikola")
    assert state
    assert state.state == "off"


async def test_sensor_update_failed_api_down(hass: HomeAssistant) -> None:
    """Test sensor is not updated if API is down."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PERSON_NAME: "Nikola",
            CONF_PERSON_EGN: EGN_SAMPLE,
            CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
        },
        unique_id=EGN_SAMPLE,
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
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED

    state = hass.states.get("binary_sensor.globi_nikola")
    assert state
    assert state.state == STATE_UNKNOWN


async def test_sensor_update_failed_api_timeout(hass: HomeAssistant) -> None:
    """Test sensor is not updated if API is down."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PERSON_NAME: "Nikola",
            CONF_PERSON_EGN: EGN_SAMPLE,
            CONF_DRIVING_LICENSE: LICENSE_SAMPLE,
        },
        unique_id=EGN_SAMPLE,
    )

    with patch(
        KAT_API_VERIFY_CREDENTIALS,
        return_value=KatApiResponse(True),
    ), patch(
        KAT_API_CHECK_OBLIGATIONS,
        return_value=KatApiResponse(False, "Error message", KatErrorType.TIMEOUT),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED

    state = hass.states.get("binary_sensor.globi_nikola")
    assert state
    assert state.state == STATE_UNKNOWN
