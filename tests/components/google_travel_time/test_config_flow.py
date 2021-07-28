"""Test the Google Maps Travel Time config flow."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.google_travel_time.const import (
    ARRIVAL_TIME,
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_LANGUAGE,
    CONF_OPTIONS,
    CONF_ORIGIN,
    CONF_TIME,
    CONF_TIME_TYPE,
    CONF_TRAFFIC_MODEL,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_TRAVEL_MODE,
    CONF_UNITS,
    DEFAULT_NAME,
    DEPARTURE_TIME,
    DOMAIN,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)

from tests.common import MockConfigEntry


async def test_minimum_fields(hass, validate_config_entry, bypass_setup):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == DEFAULT_NAME
    assert result2["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_API_KEY: "api_key",
        CONF_ORIGIN: "location1",
        CONF_DESTINATION: "location2",
    }


async def test_invalid_config_entry(hass, invalidate_config_entry):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass, validate_config_entry, bypass_update):
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
        options={
            CONF_MODE: "driving",
            CONF_ARRIVAL_TIME: "test",
            CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_LANGUAGE: "en",
            CONF_AVOID: "tolls",
            CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_TIME_TYPE: ARRIVAL_TIME,
            CONF_TIME: "test",
            CONF_TRAFFIC_MODEL: "best_guess",
            CONF_TRANSIT_MODE: "train",
            CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_ARRIVAL_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }

    assert entry.options == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_ARRIVAL_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }


async def test_options_flow_departure_time(hass, validate_config_entry, bypass_update):
    """Test options flow wiith departure time."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_LANGUAGE: "en",
            CONF_AVOID: "tolls",
            CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_TIME_TYPE: DEPARTURE_TIME,
            CONF_TIME: "test",
            CONF_TRAFFIC_MODEL: "best_guess",
            CONF_TRANSIT_MODE: "train",
            CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_DEPARTURE_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }

    assert entry.options == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_DEPARTURE_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }


async def test_dupe(hass, validate_config_entry, bypass_setup):
    """Test setting up the same entry data twice is OK."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_import_flow(hass, validate_config_entry, bypass_update):
    """Test import_flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_OPTIONS: {
                CONF_MODE: "driving",
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test_name"
    assert result["data"] == {
        CONF_API_KEY: "api_key",
        CONF_ORIGIN: "location1",
        CONF_DESTINATION: "location2",
        CONF_NAME: "test_name",
        CONF_OPTIONS: {
            CONF_MODE: "driving",
            CONF_LANGUAGE: "en",
            CONF_AVOID: "tolls",
            CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_ARRIVAL_TIME: "test",
            CONF_TRAFFIC_MODEL: "best_guess",
            CONF_TRANSIT_MODE: "train",
            CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
        },
    }

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {
        CONF_NAME: "test_name",
        CONF_API_KEY: "api_key",
        CONF_ORIGIN: "location1",
        CONF_DESTINATION: "location2",
    }
    assert entry.options == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_ARRIVAL_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }


async def test_dupe_import_no_options(hass, bypass_update):
    """Test duplicate import with no options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_dupe_import_default_options(hass, bypass_update):
    """Test duplicate import with default options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_OPTIONS: {
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_OPTIONS: {
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def _setup_dupe_import(hass, bypass_update):
    """Set up dupe import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_OPTIONS: {
                CONF_MODE: "walking",
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    await hass.async_block_till_done()


async def test_dupe_import(hass, bypass_update):
    """Test duplicate import."""
    await _setup_dupe_import(hass, bypass_update)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_OPTIONS: {
                CONF_MODE: "walking",
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_dupe_import_false_check_data_keys(hass, bypass_update):
    """Test false duplicate import check when data keys differ."""
    await _setup_dupe_import(hass, bypass_update)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key2",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_OPTIONS: {
                CONF_MODE: "walking",
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_dupe_import_false_check_no_units(hass, bypass_update):
    """Test false duplicate import check when units aren't provided."""
    await _setup_dupe_import(hass, bypass_update)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_OPTIONS: {
                CONF_MODE: "walking",
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_dupe_import_false_check_units(hass, bypass_update):
    """Test false duplicate import check when units are provided but different."""
    await _setup_dupe_import(hass, bypass_update)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_OPTIONS: {
                CONF_MODE: "walking",
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_UNITS: CONF_UNIT_SYSTEM_METRIC,
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_dupe_import_false_check_travel_mode(hass, bypass_update):
    """Test false duplicate import check when travel mode differs."""
    await _setup_dupe_import(hass, bypass_update)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_TRAVEL_MODE: "driving",
            CONF_OPTIONS: {
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_dupe_import_false_check_mode(hass, bypass_update):
    """Test false duplicate import check when mode diiffers."""
    await _setup_dupe_import(hass, bypass_update)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_OPTIONS: {
                CONF_MODE: "driving",
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_dupe_import_false_check_no_mode(hass, bypass_update):
    """Test false duplicate import check when no mode is provided."""
    await _setup_dupe_import(hass, bypass_update)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_OPTIONS: {
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_dupe_import_false_check_options(hass, bypass_update):
    """Test false duplicate import check when options differ."""
    await _setup_dupe_import(hass, bypass_update)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
            CONF_NAME: "test_name",
            CONF_OPTIONS: {
                CONF_MODE: "walking",
                CONF_AVOID: "tolls",
                CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
