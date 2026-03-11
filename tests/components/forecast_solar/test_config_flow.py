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
    DOMAIN,
    SUBENTRY_TYPE_PLANE,
)
from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
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
    assert config_entry.options == {}

    # Verify a plane subentry was created
    assert len(config_entry.subentries) == 1
    subentry = next(iter(config_entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TYPE_PLANE
    assert subentry.data == {
        CONF_DECLINATION: 42,
        CONF_AZIMUTH: 142,
        CONF_MODULES_POWER: 4242,
    }
    assert subentry.title == "42° / 142° / 4242W"

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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "solarPOWER!",
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
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "SolarForecast150",
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # With the API key
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "SolarForecast150",
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "SolarForecast150",
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Without the API key
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: None,
        CONF_DAMPING_MORNING: 0.25,
        CONF_DAMPING_EVENING: 0.25,
        CONF_INVERTER_SIZE: 2000,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_subentry_flow_add_plane(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding a plane via subentry flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DECLINATION: 45,
            CONF_AZIMUTH: 270,
            CONF_MODULES_POWER: 3000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "45° / 270° / 3000W"
    assert result["data"] == {
        CONF_DECLINATION: 45,
        CONF_AZIMUTH: 270,
        CONF_MODULES_POWER: 3000,
    }

    assert len(mock_config_entry.subentries) == 2


@pytest.mark.usefixtures("mock_setup_entry")
async def test_subentry_flow_reconfigure_plane(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring a plane via subentry flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the existing plane subentry id
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    subentry_id = next(iter(entry.subentries))

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
        context={"source": "reconfigure", "subentry_id": subentry_id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DECLINATION: 50,
            CONF_AZIMUTH: 200,
            CONF_MODULES_POWER: 6000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert len(entry.subentries) == 1
    subentry = entry.subentries[subentry_id]
    assert subentry.data == {
        CONF_DECLINATION: 50,
        CONF_AZIMUTH: 200,
        CONF_MODULES_POWER: 6000,
    }
    assert subentry.title == "50° / 200° / 6000W"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_subentry_flow_no_api_key(
    hass: HomeAssistant,
) -> None:
    """Test that adding more than one plane without API key is not allowed."""
    config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique",
        version=3,
        domain=DOMAIN,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options={},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 30,
                    CONF_AZIMUTH: 190,
                    CONF_MODULES_POWER: 5100,
                },
                subentry_id="mock_plane_id",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="30° / 190° / 5100W",
                unique_id=None,
            ),
        ],
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_PLANE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_key_required"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_subentry_flow_max_planes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that adding more than 4 planes is not allowed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # mock_config_entry already has 1 plane subentry; add 3 more to reach the limit
    for i in range(3):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
            context={"source": "user"},
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_DECLINATION: 10 * (i + 1),
                CONF_AZIMUTH: 90 * (i + 1),
                CONF_MODULES_POWER: 1000 * (i + 1),
            },
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert len(entry.subentries) == 4

    # Attempt to add a 5th plane should be aborted
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "max_planes"
