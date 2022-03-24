"""Test the Time & Date config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.time_date.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("sensor",))
async def test_config_flow(hass: HomeAssistant, platform) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.time_date.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"beat": True},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Time & Date"
    assert result["data"] == {}
    assert result["options"] == {
        "beat": True,
        "date": False,
        "date_time": False,
        "date_time_iso": False,
        "date_time_utc": False,
        "time": False,
        "time_date": False,
        "time_utc": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "beat": True,
        "date": False,
        "date_time": False,
        "date_time_iso": False,
        "date_time_utc": False,
        "time": False,
        "time_date": False,
        "time_utc": False,
    }
    assert config_entry.title == "Time & Date"


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize("platform", ("sensor",))
async def test_options(hass: HomeAssistant, platform) -> None:
    """Test reconfiguring."""
    registry = er.async_get(hass)
    time_beat_entity_id = "sensor.internet_time"
    time_utc_entity_id = "sensor.time_utc"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "beat": True,
            "date": False,
            "date_time": False,
            "date_time_iso": False,
            "date_time_utc": False,
            "time": False,
            "time_date": False,
            "time_utc": False,
        },
        title="Time & Date",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert registry.async_get(time_beat_entity_id) is not None
    assert hass.states.get(time_beat_entity_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, "beat") is True
    assert get_suggested(schema, "date") is False
    assert get_suggested(schema, "date_time") is False
    assert get_suggested(schema, "date_time_iso") is False
    assert get_suggested(schema, "date_time_utc") is False
    assert get_suggested(schema, "time") is False
    assert get_suggested(schema, "time_date") is False
    assert get_suggested(schema, "time_utc") is False

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "time_utc": True,
        },
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        "beat": False,
        "date": False,
        "date_time": False,
        "date_time_iso": False,
        "date_time_utc": False,
        "time": False,
        "time_date": False,
        "time_utc": True,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "beat": False,
        "date": False,
        "date_time": False,
        "date_time_iso": False,
        "date_time_utc": False,
        "time": False,
        "time_date": False,
        "time_utc": True,
    }
    assert config_entry.title == "Time & Date"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1
    assert registry.async_get(time_beat_entity_id) is None
    assert registry.async_get(time_utc_entity_id) is not None
    assert hass.states.get(time_utc_entity_id)


@pytest.mark.parametrize(
    "source,data",
    (
        (config_entries.SOURCE_USER, None),
        (config_entries.SOURCE_IMPORT, {"display_options": ["time_date"]}),
    ),
)
async def test_single_instance_allowed(
    hass: HomeAssistant,
    source: str,
    data: dict,
) -> None:
    """Test we abort if already setup."""
    mock_config_entry = MockConfigEntry(domain=DOMAIN)

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=data
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_import_flow(
    hass: HomeAssistant,
) -> None:
    """Test the import configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={"display_options": ["time_date"]},
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Time & Date"
    assert result["data"] == {}
    assert result["options"] == {
        "beat": False,
        "date": False,
        "date_time": False,
        "date_time_iso": False,
        "date_time_utc": False,
        "time": False,
        "time_date": True,
        "time_utc": False,
    }
