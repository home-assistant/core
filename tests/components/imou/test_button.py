"""Tests for Imou button platform."""

from unittest.mock import MagicMock

from pyimouapi.exceptions import ImouException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.imou.const import PARAM_MUTE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import UNKNOWN_BUTTON_KEY, create_online_device

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("init_integration")
async def test_button_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot button entities created from the default mock device list."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                button_keys=(UNKNOWN_BUTTON_KEY, PARAM_MUTE),
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_setup_ignores_unknown_button_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unknown button keys from the API are not turned into entities."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    assert len(entries) == 1
    assert entries[0].translation_key == PARAM_MUTE


@pytest.mark.usefixtures("init_integration")
async def test_press_button_via_service(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    init_integration: MagicMock,
) -> None:
    """Pressing a button calls the vendor library through the coordinator."""
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    mute_entry = next(e for e in entries if e.translation_key == PARAM_MUTE)
    entity_id = mute_entry.entity_id

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    init_integration.async_press_button.assert_awaited_once()
    call = init_integration.async_press_button.await_args
    assert call is not None
    assert call.args[1] == PARAM_MUTE


@pytest.mark.usefixtures("init_integration")
async def test_press_button_service_propagates_api_error(
    hass: HomeAssistant,
    init_integration: MagicMock,
) -> None:
    """Imou API errors from async_press_button surface to the service call."""
    init_integration.async_press_button.side_effect = ImouException("cloud failure")

    entity_id = hass.states.async_all("button")[0].entity_id

    with pytest.raises(HomeAssistantError, match="cloud failure"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
