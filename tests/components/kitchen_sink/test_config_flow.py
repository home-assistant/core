"""Test the Everything but the Kitchen Sink config flow."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant import config_entries, setup
from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def no_platforms() -> Generator[None]:
    """Don't enable any platforms."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [],
    ):
        yield


async def test_import(hass: HomeAssistant) -> None:
    """Test that we can import a config entry."""
    with patch("homeassistant.components.kitchen_sink.async_setup_entry"):
        assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {}


async def test_import_once(hass: HomeAssistant) -> None:
    """Test that we don't create multiple config entries."""
    with patch(
        "homeassistant.components.kitchen_sink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kitchen Sink"
    assert result["data"] == {}
    assert result["options"] == {}
    mock_setup_entry.assert_called_once()

    # Test importing again doesn't create a 2nd entry
    with patch(
        "homeassistant.components.kitchen_sink.async_setup_entry"
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    mock_setup_entry.assert_not_called()


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth works."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["handler"] == DOMAIN
    assert flows[0]["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("no_platforms")
async def test_options_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options_1"

    section_marker, section_schema = list(result["data_schema"].schema.items())[0]
    assert section_marker == "section_1"
    section_schema_markers = list(section_schema.schema.schema)
    assert len(section_schema_markers) == 2
    assert section_schema_markers[0] == "bool"
    assert section_schema_markers[0].description is None
    assert section_schema_markers[1] == "int"
    assert section_schema_markers[1].description == {"suggested_value": 10}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"section_1": {"bool": True, "int": 15}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {"section_1": {"bool": True, "int": 15}}

    await hass.async_block_till_done()


@pytest.mark.usefixtures("no_platforms")
async def test_subentry_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "entity"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_sensor"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"name": "Sensor 1", "state": 15},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry_id = list(config_entry.subentries)[0]
    assert config_entry.subentries == {
        subentry_id: config_entries.ConfigSubentry(
            data={"state": 15},
            subentry_id=subentry_id,
            subentry_type="entity",
            title="Sensor 1",
            unique_id=None,
        )
    }

    await hass.async_block_till_done()


@pytest.mark.usefixtures("no_platforms")
async def test_subentry_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    subentry_id = "mock_id"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={"state": 15},
                subentry_id="mock_id",
                subentry_type="entity",
                title="Sensor 1",
                unique_id=None,
            )
        ],
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "entity", subentry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_sensor"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"name": "Renamed sensor 1", "state": 5},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert config_entry.subentries == {
        subentry_id: config_entries.ConfigSubentry(
            data={"state": 5},
            subentry_id=subentry_id,
            subentry_type="entity",
            title="Renamed sensor 1",
            unique_id=None,
        )
    }

    await hass.async_block_till_done()
