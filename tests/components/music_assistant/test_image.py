"""Test Music Assistant image entities."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from music_assistant_models.enums import EventType
from music_assistant_models.errors import MusicAssistantError
from music_assistant_models.provider import ProviderInstance, ProviderType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.music_assistant import async_remove_config_entry_device
from homeassistant.components.music_assistant.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from .common import (
    setup_integration_from_fixtures,
    snapshot_music_assistant_entities,
    trigger_subscription_callback,
)

from tests.common import async_fire_time_changed


@pytest.fixture(autouse=True)
def mock_getrandbits() -> Generator[None]:
    """Mock image access token which normally is randomized."""
    with patch(
        "homeassistant.components.image.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


async def test_image_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test image entities."""
    freezer.move_to("2024-01-01T12:00:00+00:00")
    music_assistant_client.send_command.return_value = "http://mock-party-url"
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(hass, entity_registry, snapshot, Platform.IMAGE)


async def test_image_url_update(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test image updates when URL changes."""
    music_assistant_client.send_command.return_value = "http://mock-party-url-1"
    await setup_integration_from_fixtures(hass, music_assistant_client)

    state = hass.states.get("image.party_mode_plugin_guest_qr_code")
    assert state
    last_updated = state.state
    assert last_updated is not None

    music_assistant_client.send_command.return_value = "http://mock-party-url-2"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1))
    await hass.async_block_till_done()

    state = hass.states.get("image.party_mode_plugin_guest_qr_code")
    assert state
    assert state.state != last_updated


async def test_two_entries_same_party_instance(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that two entries with the same party instance ID get different entity unique IDs."""
    music_assistant_client.send_command.return_value = "http://mock-party-url"
    await setup_integration_from_fixtures(hass, music_assistant_client)

    # Setup second entry with a different server ID
    music_assistant_client.server_info.server_id = "second_server_id"
    await setup_integration_from_fixtures(hass, music_assistant_client)

    entities = er.async_entries_for_device(
        entity_registry,
        next(
            d.id
            for d in hass.data["device_registry"].devices.values()
            if d.identifiers == {("music_assistant", "second_server_id_party_instance")}
        ),
    )
    # The entities should be created, verifying that they did not fail due to duplicate unique IDs
    assert len(entities) > 0
    # Also verify the first entry's entities still exist
    first_entities = er.async_entries_for_device(
        entity_registry,
        next(
            d.id
            for d in hass.data["device_registry"].devices.values()
            if d.identifiers == {("music_assistant", "1234_party_instance")}
        ),
    )
    assert len(first_entities) > 0


async def test_image_url_fetch_failure_and_recovery(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test image updates when URL fetch fails or returns falsy, and recovers."""
    # Start with a valid URL
    music_assistant_client.send_command.return_value = "http://mock-party-url-1"
    await setup_integration_from_fixtures(hass, music_assistant_client)

    state = hass.states.get("image.party_mode_plugin_guest_qr_code")
    assert state
    assert state.state != STATE_UNAVAILABLE

    # Mock MusicAssistantError
    music_assistant_client.send_command.side_effect = MusicAssistantError("Error")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1))
    await hass.async_block_till_done()

    state = hass.states.get("image.party_mode_plugin_guest_qr_code")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Recover
    music_assistant_client.send_command.side_effect = None
    music_assistant_client.send_command.return_value = "http://mock-party-url-2"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()

    state = hass.states.get("image.party_mode_plugin_guest_qr_code")
    assert state
    assert state.state != STATE_UNAVAILABLE

    # Return None
    music_assistant_client.send_command.return_value = None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=3))
    await hass.async_block_till_done()

    state = hass.states.get("image.party_mode_plugin_guest_qr_code")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_party_mode_provider_lifecycle(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the provider lifecycle of Party Mode (removal and replacement)."""
    await setup_integration_from_fixtures(hass, music_assistant_client)

    # 1. Verify initial setup registers the device
    device = device_registry.async_get_device({(DOMAIN, "1234_party_instance")})
    assert device is not None

    # 2. Simulate provider removal (get_provider returns None)
    music_assistant_client.get_provider.side_effect = None
    music_assistant_client.get_provider.return_value = None
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PROVIDERS_UPDATED
    )

    # Device should NOT have config entry association removed yet
    device = device_registry.async_get_device({(DOMAIN, "1234_party_instance")})
    assert device is not None
    assert device.config_entries

    # 3. Simulate provider replacement with a new instance ID
    music_assistant_client.get_provider.return_value = ProviderInstance(
        type=ProviderType.PLUGIN,
        domain="party",
        name="New Party Mode Plugin",
        instance_id="new_party_instance",
        supported_features=set(),
        available=True,
    )
    # Trigger callback which will add the new party mode device
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PROVIDERS_UPDATED
    )

    # Now the old device should have config entry association removed
    device = device_registry.async_get_device({(DOMAIN, "1234_party_instance")})
    assert device is None or not device.config_entries

    # Verify the new device registry entry is created
    new_device = device_registry.async_get_device({(DOMAIN, "1234_new_party_instance")})
    assert new_device is not None

    # 4. Verify we cannot remove the active party device
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    with pytest.raises(HomeAssistantError) as excinfo:
        await async_remove_config_entry_device(hass, config_entry, new_device)
    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "party_mode_active_device_removal"


async def test_party_mode_core_state_update(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that QR code updates when a CORE_STATE_UPDATED event is received."""
    # Start with initial valid URL
    music_assistant_client.send_command.return_value = "http://mock-party-url-1"
    await setup_integration_from_fixtures(hass, music_assistant_client)

    state = hass.states.get("image.party_mode_plugin_guest_qr_code")
    assert state
    assert state.state != STATE_UNAVAILABLE

    entity = hass.data["entity_components"]["image"].get_entity(
        "image.party_mode_plugin_guest_qr_code"
    )
    assert entity is not None

    # Fetch initial image bytes
    bytes_1 = await entity.async_image()
    assert bytes_1 is not None

    # Simulate URL change on the server
    music_assistant_client.send_command.return_value = "http://mock-party-url-2"

    # Trigger CORE_STATE_UPDATED callback
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.CORE_STATE_UPDATED
    )

    # Fetch updated image bytes
    bytes_2 = await entity.async_image()
    assert bytes_2 is not None
    assert bytes_1 != bytes_2
