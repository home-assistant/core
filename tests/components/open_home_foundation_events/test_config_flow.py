"""Test the Open Home Foundation Events config flow."""

import pytest

from homeassistant.components.open_home_foundation_events.const import (
    DOMAIN,
    SUBENTRY_TYPE_AREA,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

AREA = {CONF_LATITUDE: 52.37, CONF_LONGITUDE: 4.89, CONF_RADIUS: 30000}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    name_key = next(key for key in result["data_schema"].schema if key == CONF_NAME)
    assert name_key.default() == "Open Home Foundation events near test home"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Amsterdam", CONF_LOCATION: AREA}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Open Home Foundation Events"
    assert result["data"] == {}
    (subentry,) = result["result"].subentries.values()
    assert subentry.subentry_type == SUBENTRY_TYPE_AREA
    assert subentry.title == "Amsterdam"
    assert dict(subentry.data) == AREA


async def test_single_instance(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test only one entry is allowed."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_add_area(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding an area subentry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_AREA),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    name_key = next(key for key in result["data_schema"].schema if key == CONF_NAME)
    assert name_key.default() == "Open Home Foundation events near test home"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Amsterdam", CONF_LOCATION: AREA}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Amsterdam"
    assert result["data"] == AREA


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_area(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring an area subentry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, "dublin-subentry-id"
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Amsterdam", CONF_LOCATION: AREA}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = mock_config_entry.subentries["dublin-subentry-id"]
    assert subentry.title == "Amsterdam"
    assert dict(subentry.data) == AREA
