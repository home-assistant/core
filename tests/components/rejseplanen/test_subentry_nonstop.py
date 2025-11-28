"""Tests for rejseplanen handling of non-stop subentries."""

from unittest.mock import MagicMock, patch

from homeassistant.components.rejseplanen.const import CONF_API_KEY, CONF_NAME, DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_async_setup_entry_skips_non_stop_subentry(hass: HomeAssistant) -> None:
    """Ensure async_setup_entry skips subentries with type != 'stop'."""

    # Create a mock main config entry that includes a non-stop subentry
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key", CONF_NAME: "Rejseplanen"},
        unique_id="rejse_nonstop",
        subentries_data=(
            ConfigSubentryData(
                data={"some_key": "some_value"},
                subentry_type="not_stop",
                title="Not a stop",
                unique_id=None,
            ),
        ),
    )

    main_entry.add_to_hass(hass)

    # Patch the internal API client to avoid network calls
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.get_departures.return_value = ([], [])
        mock_api_class.return_value = mock_api

        # Set up the entry; this should run through the subentries loop
        await hass.config_entries.async_setup(main_entry.entry_id)
        await hass.async_block_till_done()

    # Verify that no entities were registered for this config entry
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, main_entry.entry_id)
    assert len(entries) == 0
