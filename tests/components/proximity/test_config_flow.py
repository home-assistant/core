"""Test proximity config flow."""
from unittest.mock import patch

import pytest

from homeassistant.components.proximity.const import (
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    CONF_TRACKED_ENTITIES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("user_input", "expected_result"),
    [
        (
            {
                CONF_ZONE: "zone.home",
                CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
            },
            {
                CONF_ZONE: "zone.home",
                CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
                CONF_IGNORED_ZONES: [],
                CONF_TOLERANCE: 1,
            },
        ),
        (
            {
                CONF_ZONE: "zone.home",
                CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
                CONF_IGNORED_ZONES: ["zone.work"],
                CONF_TOLERANCE: 10,
            },
            {
                CONF_ZONE: "zone.home",
                CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
                CONF_IGNORED_ZONES: ["zone.work"],
                CONF_TOLERANCE: 10,
            },
        ),
    ],
)
async def test_user_flow(
    hass: HomeAssistant, user_input: dict, expected_result: dict
) -> None:
    """Test starting a flow by user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.proximity.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == expected_result

        zone = hass.states.get(user_input[CONF_ZONE])
        assert result["title"] == zone.name

        await hass.async_block_till_done()

    assert mock_setup_entry.called


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        title="home",
        data={
            CONF_ZONE: "zone.home",
            CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
            CONF_IGNORED_ZONES: ["zone.work"],
            CONF_TOLERANCE: 10,
        },
        unique_id=f"{DOMAIN}_home",
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.proximity.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()
        assert mock_setup_entry.called

        result = await hass.config_entries.options.async_init(mock_config.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRACKED_ENTITIES: ["device_tracker.test2"],
            CONF_IGNORED_ZONES: [],
            CONF_TOLERANCE: 1,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config.data == {
        CONF_ZONE: "zone.home",
        CONF_TRACKED_ENTITIES: ["device_tracker.test2"],
        CONF_IGNORED_ZONES: [],
        CONF_TOLERANCE: 1,
    }


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test import of yaml configuration."""
    with patch(
        "homeassistant.components.proximity.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_NAME: "home",
                CONF_ZONE: "zone.home",
                CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
                CONF_IGNORED_ZONES: ["zone.work"],
                CONF_TOLERANCE: 10,
                CONF_UNIT_OF_MEASUREMENT: "km",
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            CONF_NAME: "home",
            CONF_ZONE: "zone.home",
            CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
            CONF_IGNORED_ZONES: ["zone.work"],
            CONF_TOLERANCE: 10,
            CONF_UNIT_OF_MEASUREMENT: "km",
        }

        zone = hass.states.get("zone.home")
        assert result["title"] == zone.name

        await hass.async_block_till_done()

    assert mock_setup_entry.called


async def test_abort_duplicated_entry(hass: HomeAssistant) -> None:
    """Test if we abort on duplicate user input data."""
    DATA = {
        CONF_ZONE: "zone.home",
        CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
        CONF_IGNORED_ZONES: ["zone.work"],
        CONF_TOLERANCE: 10,
    }
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        title="home",
        data=DATA,
        unique_id=f"{DOMAIN}_home",
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.proximity.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=DATA,
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"

        await hass.async_block_till_done()


async def test_avoid_duplicated_title(hass: HomeAssistant) -> None:
    """Test if we avoid duplicate titles."""
    MockConfigEntry(
        domain=DOMAIN,
        title="home",
        data={
            CONF_ZONE: "zone.home",
            CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
            CONF_IGNORED_ZONES: ["zone.work"],
            CONF_TOLERANCE: 10,
        },
        unique_id=f"{DOMAIN}_home",
    ).add_to_hass(hass)

    MockConfigEntry(
        domain=DOMAIN,
        title="home 3",
        data={
            CONF_ZONE: "zone.home",
            CONF_TRACKED_ENTITIES: ["device_tracker.test2"],
            CONF_IGNORED_ZONES: ["zone.work"],
            CONF_TOLERANCE: 10,
        },
        unique_id=f"{DOMAIN}_home",
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.proximity.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_ZONE: "zone.home",
                CONF_TRACKED_ENTITIES: ["device_tracker.test3"],
                CONF_IGNORED_ZONES: [],
                CONF_TOLERANCE: 10,
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "home 2"

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_ZONE: "zone.home",
                CONF_TRACKED_ENTITIES: ["device_tracker.test4"],
                CONF_IGNORED_ZONES: [],
                CONF_TOLERANCE: 10,
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "home 4"

        await hass.async_block_till_done()
