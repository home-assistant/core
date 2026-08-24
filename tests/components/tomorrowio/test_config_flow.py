"""Test the Tomorrow.io config flow."""

from unittest.mock import patch

import pytest
from pytomorrowio.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
    UnknownException,
)

from homeassistant.components.tomorrowio.const import (
    CONF_TIMESTEP,
    DOMAIN,
    SUBENTRY_TYPE_LOCATION,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import make_v2_config_entry
from .const import API_KEY, MIN_CONFIG


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MIN_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tomorrow.io"
    assert result["data"] == {CONF_API_KEY: API_KEY}
    assert result["result"].unique_id == API_KEY


async def test_user_flow_api_key_already_configured(hass: HomeAssistant) -> None:
    """Test user config flow aborts when the API key is already configured."""
    make_v2_config_entry().add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MIN_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "errors"),
    [
        pytest.param(
            CantConnectException, {"base": "cannot_connect"}, id="cannot_connect"
        ),
        pytest.param(
            InvalidAPIKeyException,
            {CONF_API_KEY: "invalid_api_key"},
            id="invalid_api_key",
        ),
        pytest.param(
            RateLimitedException, {CONF_API_KEY: "rate_limited"}, id="rate_limited"
        ),
        pytest.param(UnknownException, {"base": "unknown"}, id="unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, side_effect: Exception, errors: dict[str, str]
) -> None:
    """Test user config flow errors."""
    with patch(
        "homeassistant.components.tomorrowio.config_flow.TomorrowioV4.realtime",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MIN_CONFIG
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MIN_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_location_subentry_flow(hass: HomeAssistant) -> None:
    """Test creating a location subentry."""
    config_entry = make_v2_config_entry()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_LOCATION),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Work",
            CONF_LOCATION: {CONF_LATITUDE: 81.0, CONF_LONGITUDE: 81.0},
            CONF_TIMESTEP: 5,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Work"

    assert len(config_entry.subentries) == 2
    subentry = next(
        subentry
        for subentry in config_entry.subentries.values()
        if subentry.unique_id == "81.0_81.0"
    )
    assert subentry.subentry_type == SUBENTRY_TYPE_LOCATION
    assert subentry.title == "Work"
    assert subentry.data == {
        CONF_NAME: "Work",
        CONF_LOCATION: {CONF_LATITUDE: 81.0, CONF_LONGITUDE: 81.0},
        CONF_TIMESTEP: 5,
    }


async def test_location_subentry_flow_already_configured(hass: HomeAssistant) -> None:
    """Test creating a location subentry for a location that already exists."""
    config_entry = make_v2_config_entry()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_LOCATION),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Work",
            CONF_LOCATION: {CONF_LATITUDE: 80.0, CONF_LONGITUDE: 80.0},
            CONF_TIMESTEP: 5,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(config_entry.subentries) == 1


async def test_location_subentry_reconfigure(hass: HomeAssistant) -> None:
    """Test reconfiguring a location subentry."""
    config_entry = make_v2_config_entry()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    subentry = next(iter(config_entry.subentries.values()))
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "New name",
            CONF_LOCATION: {CONF_LATITUDE: 82.0, CONF_LONGITUDE: 82.0},
            CONF_TIMESTEP: 30,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    updated_subentry = config_entry.subentries[subentry.subentry_id]
    assert updated_subentry.title == "New name"
    assert updated_subentry.unique_id == "82.0_82.0"
    assert updated_subentry.data == {
        CONF_NAME: "New name",
        CONF_LOCATION: {CONF_LATITUDE: 82.0, CONF_LONGITUDE: 82.0},
        CONF_TIMESTEP: 30,
    }


async def test_location_subentry_reconfigure_same_location(
    hass: HomeAssistant,
) -> None:
    """Test reconfiguring a location subentry without changing the location."""
    config_entry = make_v2_config_entry()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    subentry = next(iter(config_entry.subentries.values()))
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "New name",
            CONF_LOCATION: {CONF_LATITUDE: 80.0, CONF_LONGITUDE: 80.0},
            CONF_TIMESTEP: 1,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    updated_subentry = config_entry.subentries[subentry.subentry_id]
    assert updated_subentry.title == "New name"
    assert updated_subentry.unique_id == "80.0_80.0"
    assert updated_subentry.data[CONF_TIMESTEP] == 1


async def test_location_subentry_reconfigure_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test reconfiguring a location subentry to another configured location."""
    config_entry = make_v2_config_entry()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_LOCATION),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Work",
            CONF_LOCATION: {CONF_LATITUDE: 81.0, CONF_LONGITUDE: 81.0},
            CONF_TIMESTEP: 5,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    subentry = next(
        subentry
        for subentry in config_entry.subentries.values()
        if subentry.unique_id == "81.0_81.0"
    )
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Work",
            CONF_LOCATION: {CONF_LATITUDE: 80.0, CONF_LONGITUDE: 80.0},
            CONF_TIMESTEP: 5,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
