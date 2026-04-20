"""Test the Russound RNET config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.russound_rnet.const import (
    CONF_MODEL,
    CONF_SOURCES,
    CONF_ZONES,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    MOCK_SERIAL_CONFIG,
    MOCK_SERIAL_STEP_INPUT,
    MOCK_SOURCES,
    MOCK_TCP_CONFIG,
    MOCK_TCP_STEP_INPUT,
    MOCK_ZONES,
    MODEL,
)

from tests.common import MockConfigEntry


async def test_user_flow_tcp_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
) -> None:
    """Test TCP user flow creates an entry through all steps."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select TCP transport
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_TCP},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "tcp"

    # Enter TCP connection details
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_TCP_STEP_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    # Select model
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODEL: MODEL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sources"

    # Enter source names
    source_input = {
        f"source_{i}": name for i, name in enumerate(MOCK_SOURCES.values(), 1)
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        source_input,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zones"

    # Enter zone names
    zone_input = {
        f"zone_{key.replace('_', '_')}": name for key, name in MOCK_ZONES.items()
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        zone_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "CAA66"
    assert result["data"] == MOCK_TCP_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_serial_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
) -> None:
    """Test serial user flow creates an entry through all steps."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select Serial transport
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_SERIAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"

    # Enter serial connection details
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_SERIAL_STEP_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    # Select model
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODEL: MODEL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sources"

    # Enter source names
    source_input = {
        f"source_{i}": name for i, name in enumerate(MOCK_SOURCES.values(), 1)
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        source_input,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zones"

    # Enter zone names
    zone_input = {
        f"zone_{key.replace('_', '_')}": name for key, name in MOCK_ZONES.items()
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        zone_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "CAA66"
    assert result["data"] == MOCK_SERIAL_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_tcp_flow_cannot_connect_then_recovers(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
) -> None:
    """Test TCP flow handles connection error and recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_TCP},
    )
    assert result["step_id"] == "tcp"

    # Simulate connection failure
    mock_russound_client.connect.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_TCP_STEP_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "tcp"
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover
    mock_russound_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_TCP_STEP_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"


async def test_serial_flow_cannot_connect_then_recovers(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
) -> None:
    """Test serial flow handles connection error and recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_SERIAL},
    )
    assert result["step_id"] == "serial"

    mock_russound_client.connect.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_SERIAL_STEP_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_russound_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_SERIAL_STEP_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"


async def test_tcp_flow_duplicate_aborts(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate TCP flow aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_TCP},
    )
    assert result["step_id"] == "tcp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_TCP_STEP_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_serial_flow_duplicate_aborts(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_serial_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate serial flow aborts."""
    mock_serial_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_SERIAL},
    )
    assert result["step_id"] == "serial"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_SERIAL_STEP_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_yaml_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
) -> None:
    """Test YAML import prompts for model and pre-fills sources/zones."""
    yaml_config = {
        CONF_HOST: "192.168.1.100",
        CONF_NAME: "Russound",
        CONF_PORT: 9999,
        "zones": {1: {CONF_NAME: "Kitchen"}, 2: {CONF_NAME: "Living Room"}},
        "sources": [
            {CONF_NAME: "Sonos"},
            {CONF_NAME: "TV"},
            {CONF_NAME: "Radio"},
        ],
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=yaml_config
    )

    # Import validates connection, then shows model selection
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    # User selects model
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODEL: "cas44"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sources"

    # Sources are pre-filled from YAML — submit as-is
    source_input = {
        "source_1": "Sonos",
        "source_2": "TV",
        "source_3": "Radio",
        "source_4": "",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        source_input,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zones"

    # Zones are pre-filled from YAML — submit as-is
    zone_input = {
        "zone_1_1": "Kitchen",
        "zone_1_2": "Living Room",
        "zone_1_3": "",
        "zone_1_4": "",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        zone_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TYPE] == TYPE_TCP
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_PORT] == 9999
    assert result["data"][CONF_MODEL] == "cas44"
    assert result["data"][CONF_SOURCES] == {
        "1": "Sonos",
        "2": "TV",
        "3": "Radio",
    }
    assert result["data"][CONF_ZONES] == {
        "1_1": "Kitchen",
        "1_2": "Living Room",
    }


async def test_import_yaml_cannot_connect_aborts(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
) -> None:
    """Test YAML import aborts when connection fails."""
    mock_russound_client.connect.side_effect = TimeoutError

    yaml_config = {
        CONF_HOST: "192.168.1.100",
        CONF_NAME: "Russound",
        CONF_PORT: 9999,
        "zones": {1: {CONF_NAME: "Kitchen"}},
        "sources": [{CONF_NAME: "Sonos"}],
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=yaml_config
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_yaml_duplicate_aborts(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test YAML import aborts when entry already exists."""
    mock_config_entry.add_to_hass(hass)

    yaml_config = {
        CONF_HOST: "192.168.1.100",
        CONF_NAME: "Russound",
        CONF_PORT: 9999,
        "zones": {1: {CONF_NAME: "Kitchen"}},
        "sources": [{CONF_NAME: "Sonos"}],
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=yaml_config
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_updates_sources(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow updates source names."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_sources = {f"source_{i}": f"New Source {i}" for i in range(1, 7)}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        new_sources,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    assert entry.data[CONF_SOURCES] == {str(i): f"New Source {i}" for i in range(1, 7)}


async def test_empty_sources_and_zones_excluded(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
) -> None:
    """Test that empty source and zone names are excluded from config data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_TCP},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_TCP_STEP_INPUT,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODEL: MODEL},
    )

    # Only fill in 2 of 6 sources, leave rest empty
    source_input = {f"source_{i}": "" for i in range(1, 7)}
    source_input["source_1"] = "Sonos"
    source_input["source_3"] = "Radio"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        source_input,
    )
    assert result["step_id"] == "zones"

    # Only fill in 2 of 6 zones, leave rest empty
    zone_input = {f"zone_1_{z}": "" for z in range(1, 7)}
    zone_input["zone_1_1"] = "Kitchen"
    zone_input["zone_1_4"] = "Office"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        zone_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SOURCES] == {"1": "Sonos", "3": "Radio"}
    assert result["data"][CONF_ZONES] == {"1_1": "Kitchen", "1_4": "Office"}
