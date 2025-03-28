"""Test the Wallbox config flow."""

from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components.wallbox import config_flow
from homeassistant.components.wallbox.const import (
    CHARGER_ADDED_ENERGY_KEY,
    CHARGER_ADDED_RANGE_KEY,
    CHARGER_CHARGING_POWER_KEY,
    CHARGER_CHARGING_SPEED_KEY,
    CHARGER_DATA_KEY,
    CHARGER_MAX_AVAILABLE_POWER_KEY,
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    authorisation_response,
    authorisation_response_unauthorised,
    http_403_error,
    http_404_error,
    setup_integration,
)

from tests.common import MockConfigEntry

test_response = {
    CHARGER_CHARGING_POWER_KEY: 0,
    CHARGER_MAX_AVAILABLE_POWER_KEY: "xx",
    CHARGER_CHARGING_SPEED_KEY: 0,
    CHARGER_ADDED_RANGE_KEY: "xx",
    CHARGER_ADDED_ENERGY_KEY: "44.697",
    CHARGER_DATA_KEY: {CHARGER_MAX_CHARGING_CURRENT_KEY: 24},
}


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    flow = config_flow.WallboxConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form_cannot_authenticate(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(side_effect=http_403_error),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.pauseChargingSession",
            new=Mock(side_effect=http_403_error),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(side_effect=http_404_error),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.pauseChargingSession",
            new=Mock(side_effect=http_404_error),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_validate_input(hass: HomeAssistant) -> None:
    """Test we can validate input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.getChargerStatus",
            new=Mock(return_value=test_response),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["title"] == "Wallbox Portal"
    assert result2["data"]["station"] == "12345"


async def test_form_reauth(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test we handle reauth flow."""
    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response_unauthorised),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.getChargerStatus",
            new=Mock(return_value=test_response),
        ),
    ):
        result = await entry.start_reauth_flow(hass)

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_form_reauth_invalid(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test we handle reauth invalid flow."""
    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response_unauthorised),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.getChargerStatus",
            new=Mock(return_value=test_response),
        ),
    ):
        result = await entry.start_reauth_flow(hass)

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345678",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "reauth_invalid"}

    await hass.config_entries.async_unload(entry.entry_id)
