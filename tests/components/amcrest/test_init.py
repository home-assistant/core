"""Test the Amcrest integration init."""

from unittest.mock import AsyncMock, MagicMock, patch

from amcrest import AmcrestError

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_SERIAL, mock_async_property, setup_mock_amcrest_checker

from tests.common import MockConfigEntry


async def test_setup_entry_uses_unique_id_for_identifiers_when_serial_fetch_fails(
    hass: HomeAssistant,
) -> None:
    """Test config-entry setup uses entry.unique_id even if device serial fetch fails."""
    entry = MockConfigEntry(
        title="Amcrest SERIAL_FROM_FLOW",
        domain=DOMAIN,
        unique_id="SERIAL_FROM_FLOW",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 80,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
    )
    entry.add_to_hass(hass)

    api = MagicMock()
    mock_async_property(api, "async_serial_number", side_effect=AmcrestError)
    api.get_base_url.return_value = "http://1.2.3.4"

    async_forward = AsyncMock()

    with (
        patch("homeassistant.components.amcrest.AmcrestChecker", return_value=api),
        patch("homeassistant.components.amcrest.dr.async_get") as mock_async_get,
        patch("homeassistant.components.amcrest.DeviceInfo") as mock_device_info,
        patch("homeassistant.components.amcrest._start_event_monitor"),
        patch.object(hass.config_entries, "async_forward_entry_setups", async_forward),
    ):
        device_registry = MagicMock()
        mock_async_get.return_value = device_registry

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Device registry should be keyed by the stable unique_id, not entry_id.
    device_registry.async_get_or_create.assert_called_once()
    identifiers = device_registry.async_get_or_create.call_args.kwargs["identifiers"]
    assert identifiers == {(DOMAIN, "SERIAL_FROM_FLOW")}

    # DeviceInfo should also use the stable unique_id.
    assert mock_device_info.call_args.kwargs["identifiers"] == {
        (DOMAIN, "SERIAL_FROM_FLOW")
    }


async def test_setup_entry_requires_unique_id(hass: HomeAssistant) -> None:
    """Test config-entry setup fails when entry.unique_id is missing."""
    entry = MockConfigEntry(
        title="Amcrest Camera",
        domain=DOMAIN,
        unique_id=None,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 80,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
    )
    entry.add_to_hass(hass)

    api = MagicMock()
    api.get_base_url.return_value = "http://1.2.3.4"

    with patch("homeassistant.components.amcrest.AmcrestChecker", return_value=api):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_loads_platforms(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test config entry setup loads all platforms and stores runtime data."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.amcrest.AmcrestChecker") as mock_checker,
        patch("homeassistant.components.amcrest._start_event_monitor"),
    ):
        setup_mock_amcrest_checker(mock_checker)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data["device"] is not None
    assert mock_config_entry.runtime_data["stop_event"] is not None

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    platforms = {entry.entity_id.split(".")[0] for entry in entities}
    assert platforms == {
        Platform.BINARY_SENSOR,
        Platform.CAMERA,
        Platform.SENSOR,
        Platform.SWITCH,
    }

    unique_ids = {entry.unique_id for entry in entities}
    assert f"{TEST_SERIAL}-audio_detected-0" in unique_ids
    assert f"{TEST_SERIAL}-0-0" in unique_ids
    assert f"{TEST_SERIAL}-privacy_mode-0" in unique_ids


async def test_unload_entry(
    hass: HomeAssistant,
    loaded_config_entry: MockConfigEntry,
) -> None:
    """Test config entry unload sets stop_event and unloads platforms."""
    stop_event = loaded_config_entry.runtime_data["stop_event"]

    assert await hass.config_entries.async_unload(loaded_config_entry.entry_id)
    await hass.async_block_till_done()

    assert stop_event.is_set()
    assert loaded_config_entry.state is ConfigEntryState.NOT_LOADED
