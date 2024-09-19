"""Test config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.domika.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_config_setup(hass: HomeAssistant) -> None:
    """Test that config entry created only once."""
    # Create entry with default options.
    with patch(
        "homeassistant.components.domika.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == DOMAIN
    assert result.get("version") == 1
    assert result.get("minor_version") == 0
    assert result.get("options") == {
        "critical_entities": {
            "smoke_select_all": False,
            "moisture_select_all": False,
            "co_select_all": False,
            "gas_select_all": False,
            "critical_included_entity_ids": [],
        },
    }
    mock_setup_entry.assert_called_once()

    # Test that initializing again doesn't create a second entry.
    with patch(
        "homeassistant.components.domika.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"
    mock_setup_entry.assert_not_called()


@pytest.mark.parametrize(
    ("options", "expected_options"),
    [
        (
            {},
            {
                "critical_entities": {
                    "smoke_select_all": False,
                    "moisture_select_all": False,
                    "co_select_all": False,
                    "gas_select_all": False,
                    "critical_included_entity_ids": [],
                }
            },
        ),
        (
            {
                "smoke_select_all": True,
                "moisture_select_all": True,
                "co_select_all": True,
                "gas_select_all": True,
                "critical_included_entity_ids": [],
            },
            {
                "critical_entities": {
                    "smoke_select_all": True,
                    "moisture_select_all": True,
                    "co_select_all": True,
                    "gas_select_all": True,
                    "critical_included_entity_ids": [],
                }
            },
        ),
    ],
)
async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    options: dict,
    expected_options: dict,
) -> None:
    """Test options config flow."""
    mock_config_entry.add_to_hass(hass)

    # Mock async_setup_entry and async_setup. We don't want to do real setup here.
    with (
        patch(
            "homeassistant.components.domika.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.domika.async_setup",
            return_value=True,
        ) as mock_setup,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    mock_setup_entry.assert_called_once()
    mock_setup.assert_called_once()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "critical_entities"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=options,
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("data") == expected_options

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert entry.options == expected_options

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
