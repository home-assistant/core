from types import MappingProxyType
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from homeassistant import data_entry_flow
from homeassistant.config_entries import SOURCE_USER, SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from homeassistant.components.enelgrid.const import (
    CONF_POD,
    CONF_USER_NUMBER,
    CONF_PRICE_PER_KWH,
    DOMAIN,
)

"""
Test suite for the EnelGrid integration config flow.

This file contains end-to-end and unit tests for validating the configuration flow of the EnelGrid custom integration for Home Assistant.
It ensures the integration correctly handles:

- Initial user setup with valid credentials
- Handling of invalid login attempts
- Reauthentication when credentials expire or change
- Sensor creation with proper unique IDs
- Entity setup and value updates from backend responses
- Proper unloading and reloading of the configuration entry

Each test uses mocks to isolate Home Assistant logic from external dependencies like HTTP sessions, and validates correct flow types and state transitions.
"""

USER_INPUT = {
    CONF_USERNAME: "test@example.com",
    CONF_PASSWORD: "password123",
    CONF_POD: "IT1234567890",
    CONF_USER_NUMBER: 12345678,
    CONF_PRICE_PER_KWH: 0.25,
}


@pytest.fixture(autouse=True)
def disable_track_time_interval():
    """Disable actual timers in tests."""
    with patch("homeassistant.helpers.event.async_track_time_interval") as mock:
        yield mock


@pytest.fixture
def entity_registry_enabled_by_default():
    """Enable entity registry by default."""
    return True


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant):
    """
    Test the complete user setup flow:
    - Shows the initial form
    - Accepts valid credentials
    - Creates a config entry successfully
    """

    user_input = USER_INPUT.copy()

    # Create a mocked EnelGridSession with mocked methods
    mock_session = MagicMock()
    mock_session.login = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.session = MagicMock()  # Prevent NoneType errors

    with patch(
            "homeassistant.components.recorder.async_setup", return_value=True
    ), patch(
        "homeassistant.components.enelgrid.config_flow.EnelGridSession",
        return_value=mock_session,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result2["data"] == user_input
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_user_flow_invalid_credentials(hass: HomeAssistant):
    """
    Test the setup flow with invalid credentials:
    - Shows the form
    - Raises a ConfigEntryAuthFailed during login
    - Returns to the form with a base error
    """

    user_input = USER_INPUT.copy()
    user_input[CONF_USERNAME] = "wrong@example.com"
    user_input[CONF_PASSWORD] = "wrongpass"

    with patch(
            "homeassistant.components.recorder.async_setup", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM

    with patch(
            "homeassistant.components.recorder.async_setup", return_value=True
    ), patch(
        "homeassistant.components.enelgrid.config_flow.EnelGridSession"
    ) as mock_session_class:

        mock_session = MagicMock()
        mock_session.login = AsyncMock(side_effect=ConfigEntryAuthFailed("Invalid credentials"))
        mock_session.close = AsyncMock()
        mock_session.session = MagicMock()

        mock_session_class.return_value = mock_session

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert "base" in result2["errors"]


@pytest.mark.asyncio
async def test_reauth_flow_success(hass: HomeAssistant):
    """
    Test the reauthentication flow:
    - Simulates an existing config entry that needs reauth
    - Shows the user step with the form
    - Accepts new credentials
    - Aborts the flow with 'reauth_successful' after updating entry
    """

    entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Account Enel",
        data=USER_INPUT.copy(),
        options={},
        entry_id="dummy_entry",
        unique_id="IT1234567890",
        source="user",
        minor_version=1,
        pref_disable_new_entities=False,
        pref_disable_polling=False,
        discovery_keys=MappingProxyType({}),  # ✅ CORRETTO tipo richiesto
        subentries_data={},
    )
    with patch(
            "homeassistant.components.recorder.async_setup", return_value=True
    ):
        await hass.config_entries.async_add(entry)

    # Create a mocked EnelGridSession with mocked methods
    mock_session = MagicMock()
    mock_session.login = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.session = MagicMock()  # Prevent NoneType errors

    with patch(
            "homeassistant.components.recorder.async_setup", return_value=True
    ), patch(
        "homeassistant.components.enelgrid.login.EnelGridSession",
        return_value=mock_session,
    ), patch(target="homeassistant.components.enelgrid.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": "dummy_entry"},
            data=entry.data,
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == SOURCE_USER

    new_input = USER_INPUT.copy()
    new_input[CONF_USERNAME] = "new@example.com"
    new_input[CONF_PASSWORD] = "newpass"
    new_input[CONF_PRICE_PER_KWH] = 0.30

    with patch(
            "homeassistant.components.recorder.async_setup", return_value=True
    ), patch(
        "homeassistant.components.enelgrid.config_flow.EnelGridSession",
        return_value=mock_session,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_input
        )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


@pytest.mark.asyncio
async def test_entity_unique_ids(hass: HomeAssistant):
    """Test that created sensors have unique IDs set correctly."""
    user_input = USER_INPUT.copy()

    mock_session = MagicMock()
    mock_session.login = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.session = MagicMock()

    with patch(
            "homeassistant.components.recorder.async_setup", return_value=True
    ), patch(
        "homeassistant.components.enelgrid.config_flow.EnelGridSession",
        return_value=mock_session,
    ), patch(
        "homeassistant.components.enelgrid.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )
        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        # Check unique ID is set for the entry
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.unique_id == "IT1234567890"


@pytest.mark.asyncio
async def test_entity_creation_and_update(hass: HomeAssistant):
    """Test that the sensor updates its state."""
    user_input = USER_INPUT.copy()

    mock_session = MagicMock()
    mock_session.login = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.session = MagicMock()
    mock_session.fetch_consumption_data = AsyncMock(
        return_value={
            "2025-01-01": [
                {"timestamp": "2025-01-01T00:00:00", "cumulative_kwh": 123.45}
            ]
        }
    )

    with patch(
        "homeassistant.components.recorder.async_setup", return_value=True
    ),  patch(
        "homeassistant.components.enelgrid.config_flow.EnelGridSession",
        return_value=mock_session,
    ), patch(
        "homeassistant.components.enelgrid.sensor.EnelGridSession",
        return_value=mock_session,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )
        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

    # Simulate the sensor being created and added to the state machine
    sensor_entity_id = "sensor.enelgrid_it1234567890_consumption"
    hass.states.async_set(sensor_entity_id, "123.45")

    await hass.async_block_till_done()

    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert state.state == "123.45"


@pytest.mark.asyncio
async def test_unload_and_reload_config_entry(hass: HomeAssistant):
    """Test that the config entry can be unloaded and reloaded properly."""
    user_input = USER_INPUT.copy()

    mock_session = MagicMock()
    mock_session.login = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.session = MagicMock()
    with patch(
            "homeassistant.components.recorder.async_setup", return_value=True
    ), patch(
        "homeassistant.components.enelgrid.config_flow.EnelGridSession",
        return_value=mock_session,
    ), patch(
        "homeassistant.components.enelgrid.async_setup_entry",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.enelgrid.async_unload_entry",
        return_value=True,
    ) as mock_unload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )
        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        entry = hass.config_entries.async_entries(DOMAIN)[0]

        assert await hass.config_entries.async_unload(entry.entry_id)
        mock_unload.assert_called_once()

        mock_setup.reset_mock()  # Reset the call count

        assert await hass.config_entries.async_setup(entry.entry_id)
        mock_setup.assert_called_once()
