"""Test the Forecast.Solar config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.forecast_solar.const import (
    CONF_AZIMUTH,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    CONF_PLANES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Name",
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
            CONF_AZIMUTH: 142,
            CONF_DECLINATION: 42,
            CONF_MODULES_POWER: 4242,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.title == "Name"
    assert config_entry.unique_id is None
    assert config_entry.data == {
        CONF_LATITUDE: 52.42,
        CONF_LONGITUDE: 4.42,
    }
    assert config_entry.options == {
        CONF_AZIMUTH: 142,
        CONF_DECLINATION: 42,
        CONF_MODULES_POWER: 4242,
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_invalid_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options config flow when API key is invalid."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    # Select settings from menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "settings"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "solarPOWER!",
            CONF_DECLINATION: 21,
            CONF_AZIMUTH: 22,
            CONF_MODULES_POWER: 2122,
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}

    # Ensure we can recover from this error
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "SolarForecast150",
            CONF_DECLINATION: 21,
            CONF_AZIMUTH: 22,
            CONF_MODULES_POWER: 2122,
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "SolarForecast150",
        CONF_DECLINATION: 21,
        CONF_AZIMUTH: 22,
        CONF_MODULES_POWER: 2122,
        CONF_DAMPING_MORNING: 0.25,
        CONF_DAMPING_EVENING: 0.25,
        CONF_INVERTER_SIZE: 2000,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow options."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    # Select settings from menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "settings"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"

    # With the API key
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "SolarForecast150",
            CONF_DECLINATION: 21,
            CONF_AZIMUTH: 22,
            CONF_MODULES_POWER: 2122,
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "SolarForecast150",
        CONF_DECLINATION: 21,
        CONF_AZIMUTH: 22,
        CONF_MODULES_POWER: 2122,
        CONF_DAMPING_MORNING: 0.25,
        CONF_DAMPING_EVENING: 0.25,
        CONF_INVERTER_SIZE: 2000,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_without_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow options."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    # Select settings from menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "settings"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"

    # Without the API key
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DECLINATION: 21,
            CONF_AZIMUTH: 22,
            CONF_MODULES_POWER: 2122,
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: None,
        CONF_DECLINATION: 21,
        CONF_AZIMUTH: 22,
        CONF_MODULES_POWER: 2122,
        CONF_DAMPING_MORNING: 0.25,
        CONF_DAMPING_EVENING: 0.25,
        CONF_INVERTER_SIZE: 2000,
    }


@pytest.fixture
def mock_config_entry_no_api_key() -> MockConfigEntry:
    """Return a mocked config entry without API key."""
    return MockConfigEntry(
        title="Green House",
        unique_id="unique_no_api",
        version=2,
        domain=DOMAIN,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options={
            CONF_DECLINATION: 30,
            CONF_AZIMUTH: 190,
            CONF_MODULES_POWER: 5100,
            CONF_DAMPING_MORNING: 0.5,
            CONF_DAMPING_EVENING: 0.5,
            CONF_INVERTER_SIZE: 2000,
        },
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_add_plane_without_api_key(
    hass: HomeAssistant,
    mock_config_entry_no_api_key: MockConfigEntry,
) -> None:
    """Test that adding a plane without API key shows abort message."""
    mock_config_entry_no_api_key.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_no_api_key.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry_no_api_key.entry_id
    )

    assert result["type"] is FlowResultType.MENU

    # Select add_plane without API key
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "add_plane"},
    )

    # Should abort with api_key_required message
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_key_required"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_with_api_key_shows_menu(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow options with API key shows menu."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # With API key, should show menu
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    assert result["menu_options"] == ["settings", "add_plane", "remove_plane"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_add_plane(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding an additional plane."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.MENU

    # Select add_plane
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "add_plane"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_plane"

    # Add a new plane
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DECLINATION: 45,
            CONF_AZIMUTH: 270,
            CONF_MODULES_POWER: 3000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_PLANES in result["data"]
    assert len(result["data"][CONF_PLANES]) == 1
    assert result["data"][CONF_PLANES][0] == {
        CONF_DECLINATION: 45,
        CONF_AZIMUTH: 270,
        CONF_MODULES_POWER: 3000,
    }


@pytest.fixture
def mock_config_entry_with_planes() -> MockConfigEntry:
    """Return a mocked config entry with additional planes."""
    return MockConfigEntry(
        title="Green House",
        unique_id="unique_planes",
        version=2,
        domain=DOMAIN,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options={
            CONF_API_KEY: "abcdef12345678",
            CONF_DECLINATION: 30,
            CONF_AZIMUTH: 190,
            CONF_MODULES_POWER: 5100,
            CONF_DAMPING_MORNING: 0.5,
            CONF_DAMPING_EVENING: 0.5,
            CONF_INVERTER_SIZE: 2000,
            CONF_PLANES: [
                {
                    CONF_DECLINATION: 45,
                    CONF_AZIMUTH: 270,
                    CONF_MODULES_POWER: 3000,
                },
            ],
        },
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_remove_plane(
    hass: HomeAssistant,
    mock_config_entry_with_planes: MockConfigEntry,
) -> None:
    """Test removing an additional plane."""
    mock_config_entry_with_planes.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_planes.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry_with_planes.entry_id
    )

    assert result["type"] is FlowResultType.MENU

    # Select remove_plane
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "remove_plane"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "remove_plane"

    # Remove the plane
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "plane_indices": ["0"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_PLANES not in result["data"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_remove_plane_no_planes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test remove plane aborts when no planes configured."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.MENU

    # Select remove_plane when there are no planes
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "remove_plane"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_planes_to_remove"


@pytest.fixture
def mock_config_entry_with_max_planes() -> MockConfigEntry:
    """Return a mocked config entry with maximum planes."""
    return MockConfigEntry(
        title="Green House",
        unique_id="unique_max_planes",
        version=2,
        domain=DOMAIN,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options={
            CONF_API_KEY: "abcdef12345678",
            CONF_DECLINATION: 30,
            CONF_AZIMUTH: 190,
            CONF_MODULES_POWER: 5100,
            CONF_DAMPING_MORNING: 0.5,
            CONF_DAMPING_EVENING: 0.5,
            CONF_INVERTER_SIZE: 2000,
            CONF_PLANES: [
                {CONF_DECLINATION: 45, CONF_AZIMUTH: 270, CONF_MODULES_POWER: 3000},
                {CONF_DECLINATION: 30, CONF_AZIMUTH: 90, CONF_MODULES_POWER: 2500},
                {CONF_DECLINATION: 20, CONF_AZIMUTH: 180, CONF_MODULES_POWER: 2000},
            ],
        },
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_add_plane_max_reached(
    hass: HomeAssistant,
    mock_config_entry_with_max_planes: MockConfigEntry,
) -> None:
    """Test add plane aborts when maximum planes reached."""
    mock_config_entry_with_max_planes.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_max_planes.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry_with_max_planes.entry_id
    )

    assert result["type"] is FlowResultType.MENU

    # Select add_plane when max planes reached
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "add_plane"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "max_planes_reached"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_settings_preserves_planes(
    hass: HomeAssistant,
    mock_config_entry_with_planes: MockConfigEntry,
) -> None:
    """Test that updating settings preserves existing planes."""
    mock_config_entry_with_planes.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_planes.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry_with_planes.entry_id
    )

    assert result["type"] is FlowResultType.MENU

    # Select settings
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "settings"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"

    # Update settings
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "abcdef1234567890",
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 180,
            CONF_MODULES_POWER: 6000,
            CONF_DAMPING_MORNING: 0.3,
            CONF_DAMPING_EVENING: 0.3,
            CONF_INVERTER_SIZE: 3000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Verify planes are preserved
    assert CONF_PLANES in result["data"]
    assert len(result["data"][CONF_PLANES]) == 1
    assert result["data"][CONF_PLANES][0] == {
        CONF_DECLINATION: 45,
        CONF_AZIMUTH: 270,
        CONF_MODULES_POWER: 3000,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_removing_api_key_preserves_planes(
    hass: HomeAssistant,
    mock_config_entry_with_planes: MockConfigEntry,
) -> None:
    """Test that removing API key preserves additional planes."""
    mock_config_entry_with_planes.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_planes.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry_with_planes.entry_id
    )

    assert result["type"] is FlowResultType.MENU

    # Select settings
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "settings"},
    )

    assert result["type"] is FlowResultType.FORM

    # Update settings, removing API key
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 180,
            CONF_MODULES_POWER: 6000,
            CONF_DAMPING_MORNING: 0.3,
            CONF_DAMPING_EVENING: 0.3,
            CONF_INVERTER_SIZE: 3000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Verify planes are preserved even when API key is removed
    assert CONF_PLANES in result["data"]
    assert len(result["data"][CONF_PLANES]) == 1
    assert result["data"][CONF_PLANES][0] == {
        CONF_DECLINATION: 45,
        CONF_AZIMUTH: 270,
        CONF_MODULES_POWER: 3000,
    }
