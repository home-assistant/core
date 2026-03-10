"""Tests for the Kaiterra config flow."""

from __future__ import annotations

from homeassistant.components.kaiterra.const import (
    CONF_AQI_STANDARD,
    CONF_PREFERRED_UNITS,
    DEFAULT_AQI_STANDARD,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import (
    API_KEY,
    DEVICE_ID,
    DEVICE_NAME,
    DEVICE_TYPE,
    NEW_API_KEY,
    add_device_subentry,
)
from tests.common import MockConfigEntry


async def test_user_flow_creates_parent_entry(hass: HomeAssistant) -> None:
    """Test the user flow creates a parent entry from an API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: API_KEY},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kaiterra"
    assert result["data"] == {CONF_API_KEY: API_KEY}
    assert result["options"] == {
        CONF_AQI_STANDARD: DEFAULT_AQI_STANDARD,
        CONF_PREFERRED_UNITS: [],
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
    }


async def test_user_flow_aborts_for_duplicate_parent(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test the user flow aborts for a duplicate API key."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: API_KEY},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_device_subentry_flow_creates_subentry_and_reloads(
    hass: HomeAssistant,
    mock_config_entry,
    mock_validate_device,
    mock_latest_sensor_readings,
) -> None:
    """Test the device subentry flow adds a device and reloads the entry."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_TYPE: DEVICE_TYPE,
            CONF_NAME: DEVICE_NAME,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_NAME
    assert result["data"] == {
        CONF_DEVICE_ID: DEVICE_ID,
        CONF_TYPE: DEVICE_TYPE,
        CONF_NAME: DEVICE_NAME,
    }
    assert len(mock_config_entry.subentries) == 1
    assert mock_validate_device.await_count == 2
    assert hass.states.get("sensor.office_temperature") is not None
    assert hass.states.get("sensor.office_humidity") is not None
    assert hass.states.get("air_quality.office_air_quality") is not None


async def test_device_subentry_flow_aborts_for_duplicate_device(
    hass: HomeAssistant,
    mock_config_entry,
    mock_validate_device,
    mock_latest_sensor_readings,
) -> None:
    """Test duplicate device subentries are rejected."""
    add_device_subentry(hass, mock_config_entry)
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_TYPE: DEVICE_TYPE,
            CONF_NAME: DEVICE_NAME,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_device_subentry_flow_missing_device(
    hass: HomeAssistant,
    mock_config_entry,
    mock_validate_device_not_found,
    mock_latest_sensor_readings,
) -> None:
    """Test device subentry validation errors are surfaced."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_TYPE: DEVICE_TYPE,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "device_not_found"}


async def test_import_flow_creates_parent_entry_and_device_subentries(
    hass: HomeAssistant,
    mock_validate_device,
    mock_latest_sensor_readings,
) -> None:
    """Test YAML import creates a parent entry and subentries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_API_KEY: API_KEY,
            CONF_AQI_STANDARD: "cn",
            CONF_PREFERRED_UNITS: ["F", "%"],
            CONF_SCAN_INTERVAL: 45,
            "devices": [
                {
                    CONF_DEVICE_ID: DEVICE_ID,
                    CONF_TYPE: DEVICE_TYPE,
                    CONF_NAME: DEVICE_NAME,
                },
                {
                    CONF_DEVICE_ID: "device-456",
                    CONF_TYPE: "laseregg",
                    CONF_NAME: "Bedroom",
                },
            ],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: API_KEY}
    assert result["options"] == {
        CONF_AQI_STANDARD: "cn",
        CONF_PREFERRED_UNITS: ["F", "%"],
        CONF_SCAN_INTERVAL: 45,
    }
    assert len(result["subentries"]) == 2
    assert result["subentries"][0]["title"] == DEVICE_NAME
    assert result["subentries"][1]["title"] == "Bedroom"


async def test_import_flow_updates_existing_entry(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test YAML import updates an existing parent entry and its devices."""
    add_device_subentry(hass, mock_config_entry, name="Old name")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_API_KEY: API_KEY,
            CONF_AQI_STANDARD: "cn",
            CONF_PREFERRED_UNITS: ["F"],
            CONF_SCAN_INTERVAL: 60,
            "devices": [
                {
                    CONF_DEVICE_ID: DEVICE_ID,
                    CONF_TYPE: DEVICE_TYPE,
                    CONF_NAME: DEVICE_NAME,
                }
            ],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.options[CONF_AQI_STANDARD] == "cn"
    assert mock_config_entry.options[CONF_PREFERRED_UNITS] == ["F"]
    assert mock_config_entry.options[CONF_SCAN_INTERVAL] == 60
    assert next(iter(mock_config_entry.subentries.values())).title == DEVICE_NAME


async def test_import_flow_updates_existing_import_entry_when_api_key_changes(
    hass: HomeAssistant,
) -> None:
    """Test YAML import reuses the imported parent entry when the API key changes."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kaiterra",
        source=SOURCE_IMPORT,
        data={CONF_API_KEY: "old-api-key"},
    )
    mock_config_entry.add_to_hass(hass)
    add_device_subentry(hass, mock_config_entry, name="Old name")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_API_KEY: API_KEY,
            CONF_AQI_STANDARD: "cn",
            CONF_PREFERRED_UNITS: ["F"],
            CONF_SCAN_INTERVAL: 60,
            "devices": [
                {
                    CONF_DEVICE_ID: DEVICE_ID,
                    CONF_TYPE: DEVICE_TYPE,
                    CONF_NAME: DEVICE_NAME,
                }
            ],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.data[CONF_API_KEY] == API_KEY
    assert next(iter(mock_config_entry.subentries.values())).title == DEVICE_NAME


async def test_reauth_flow_updates_api_key(
    hass: HomeAssistant,
    mock_config_entry,
    mock_validate_device,
    mock_latest_sensor_readings,
) -> None:
    """Test reauth updates the API key on the parent entry."""
    add_device_subentry(hass, mock_config_entry)
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: NEW_API_KEY},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == NEW_API_KEY


async def test_options_flow_updates_parent_options(
    hass: HomeAssistant,
    mock_config_entry,
    mock_latest_sensor_readings,
) -> None:
    """Test the parent options flow updates account settings."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_AQI_STANDARD: "cn",
            CONF_PREFERRED_UNITS: ["F", "%"],
            CONF_SCAN_INTERVAL: 45,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_AQI_STANDARD: "cn",
        CONF_PREFERRED_UNITS: ["F", "%"],
        CONF_SCAN_INTERVAL: 45,
    }
