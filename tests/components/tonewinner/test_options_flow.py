"""Test the ToneWinner AT-500 options flow."""

from homeassistant.components.tonewinner.const import (
    CONF_BAUD_RATE,
    CONF_SERIAL_PORT,
    CONF_SOURCE_MAPPINGS,
    DOMAIN,
)
from homeassistant.components.tonewinner.media_player import INPUT_SOURCES
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_options_flow_init(hass: HomeAssistant, mock_config_entry) -> None:
    """Test options flow initialization."""
    mock_config_entry.add_to_hass(hass)

    # Initialize options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Verify schema contains fields for serial port configuration
    data_schema = result["data_schema"]
    assert data_schema is not None
    schema = data_schema.schema
    assert CONF_SERIAL_PORT in schema
    assert CONF_BAUD_RATE in schema

    # Verify schema contains fields for all input sources
    for source_code in INPUT_SOURCES.values():
        assert f"{source_code}_enabled" in schema
        assert f"{source_code}_name" in schema


async def test_options_flow_with_defaults(
    hass: HomeAssistant,
) -> None:
    """Test options flow shows default values when no options are set."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM

    # All sources should be enabled by default with original names
    data_schema = result["data_schema"]
    assert data_schema is not None


async def test_options_flow_with_existing_mappings(
    hass: HomeAssistant,
) -> None:
    """Test options flow loads existing source mappings."""
    # Set up existing options
    source_mappings = {
        "HD1": {"enabled": True, "name": "Living Room TV"},
        "HD2": {"enabled": False, "name": "Bedroom TV"},
        "BT": {"enabled": True, "name": "Bluetooth Audio"},
    }

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={CONF_SOURCE_MAPPINGS: source_mappings},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    data_schema = result["data_schema"]
    assert data_schema is not None


async def test_options_flow_save_mappings(
    hass: HomeAssistant,
) -> None:
    """Test saving source mappings in options flow."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    # Initialize options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # Prepare user input for a few sources
    user_input = {}
    for source_name, source_code in list(INPUT_SOURCES.items())[:3]:
        user_input[f"{source_code}_enabled"] = True
        user_input[f"{source_code}_name"] = f"Custom {source_name}"

    # Submit form
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ""

    # Verify source_mappings are saved correctly
    assert CONF_SOURCE_MAPPINGS in result["data"]
    source_mappings = result["data"][CONF_SOURCE_MAPPINGS]

    # Check that we have mappings for the sources we configured
    for source_name, source_code in list(INPUT_SOURCES.items())[:3]:
        assert source_code in source_mappings
        assert source_mappings[source_code]["enabled"] is True
        assert source_mappings[source_code]["name"] == f"Custom {source_name}"


async def test_options_flow_disable_source(
    hass: HomeAssistant,
) -> None:
    """Test disabling a source in options flow."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # Disable HDMI 1
    user_input = {
        "HD1_enabled": False,
        "HD1_name": "HDMI 1",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    source_mappings = result["data"][CONF_SOURCE_MAPPINGS]

    assert source_mappings["HD1"]["enabled"] is False
    assert source_mappings["HD1"]["name"] == "HDMI 1"


async def test_options_flow_rename_source(
    hass: HomeAssistant,
) -> None:
    """Test renaming a source in options flow."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # Rename Bluetooth source
    custom_name = "My Bluetooth Speaker"
    user_input = {
        "BT_enabled": True,
        "BT_name": custom_name,
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    source_mappings = result["data"][CONF_SOURCE_MAPPINGS]

    assert source_mappings["BT"]["name"] == custom_name


async def test_options_flow_all_sources(
    hass: HomeAssistant,
) -> None:
    """Test configuring all input sources."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # Configure all sources
    user_input = {}
    for source_name, source_code in INPUT_SOURCES.items():
        user_input[f"{source_code}_enabled"] = True
        user_input[f"{source_code}_name"] = source_name

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    source_mappings = result["data"][CONF_SOURCE_MAPPINGS]

    # Verify all sources are configured
    assert len(source_mappings) == len(INPUT_SOURCES)
    for source_code in INPUT_SOURCES.values():
        assert source_code in source_mappings


async def test_options_flow_partial_configuration(
    hass: HomeAssistant,
) -> None:
    """Test that configured sources are saved with correct values."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # Configure a few sources (what user would actually do)
    user_input = {
        "HD1_enabled": True,
        "HD1_name": "HDMI 1",
        "HD2_enabled": True,
        "HD2_name": "HDMI 2",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    source_mappings = result["data"][CONF_SOURCE_MAPPINGS]

    # Should have all sources with our configured ones having custom values
    assert "HD1" in source_mappings
    assert "HD2" in source_mappings
    assert source_mappings["HD1"]["name"] == "HDMI 1"
    assert source_mappings["HD2"]["enabled"] is True
    assert source_mappings["HD2"]["name"] == "HDMI 2"


async def test_options_flow_change_serial_and_sources(
    hass: HomeAssistant,
) -> None:
    """Test changing both serial port and source mappings together."""
    # Start with existing mappings
    existing_mappings = {
        "HD1": {"enabled": True, "name": "Living Room TV"},
        "HD2": {"enabled": False, "name": "Bedroom TV"},
    }

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={CONF_SOURCE_MAPPINGS: existing_mappings},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # Update both serial port and source mappings
    user_input = {
        CONF_SERIAL_PORT: "/dev/ttyAMA0",
        CONF_BAUD_RATE: 19200,
        "HD1_enabled": False,  # Disable it
        "HD1_name": "New Living Room TV",
        "HD2_enabled": True,  # Enable it
        "HD2_name": "New Bedroom TV",
        "BT_enabled": True,
        "BT_name": "Bluetooth Audio",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify entry data was updated with new serial port settings
    assert mock_config_entry.data[CONF_SERIAL_PORT] == "/dev/ttyAMA0"
    assert mock_config_entry.data[CONF_BAUD_RATE] == 19200

    # Verify source mappings were updated correctly
    source_mappings = result["data"][CONF_SOURCE_MAPPINGS]
    assert source_mappings["HD1"]["enabled"] is False
    assert source_mappings["HD1"]["name"] == "New Living Room TV"
    assert source_mappings["HD2"]["enabled"] is True
    assert source_mappings["HD2"]["name"] == "New Bedroom TV"
    assert source_mappings["BT"]["enabled"] is True
    assert source_mappings["BT"]["name"] == "Bluetooth Audio"


async def test_options_flow_change_serial_port(
    hass: HomeAssistant,
) -> None:
    """Test changing serial port configuration in options flow."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # Change serial port settings
    user_input = {
        CONF_SERIAL_PORT: "/dev/ttyUSB1",
        CONF_BAUD_RATE: 115200,
        "HD1_enabled": True,
        "HD1_name": "HDMI 1",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ""

    # Verify entry data was updated with new serial port settings
    assert mock_config_entry.data[CONF_SERIAL_PORT] == "/dev/ttyUSB1"
    assert mock_config_entry.data[CONF_BAUD_RATE] == 115200

    # Verify source mappings are still saved
    source_mappings = result["data"][CONF_SOURCE_MAPPINGS]
    assert "HD1" in source_mappings


async def test_options_flow_update_existing(
    hass: HomeAssistant,
) -> None:
    """Test updating existing source mappings."""
    # Start with existing mappings
    existing_mappings = {
        "HD1": {"enabled": True, "name": "Old Name"},
        "HD2": {"enabled": False, "name": "HDMI 2"},
    }

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={CONF_SOURCE_MAPPINGS: existing_mappings},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # Update the mappings
    user_input = {
        "HD1_enabled": False,  # Disable it
        "HD1_name": "New Name",  # Rename it
        "HD2_enabled": True,  # Enable it
        "HD2_name": "HDMI 2",  # Keep name
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    source_mappings = result["data"][CONF_SOURCE_MAPPINGS]

    assert source_mappings["HD1"]["enabled"] is False
    assert source_mappings["HD1"]["name"] == "New Name"
    assert source_mappings["HD2"]["enabled"] is True
    assert source_mappings["HD2"]["name"] == "HDMI 2"
