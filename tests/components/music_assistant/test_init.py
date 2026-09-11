"""Test the Music Assistant integration init."""

from unittest.mock import AsyncMock, MagicMock

from music_assistant_models.dashboard import DashboardDevice
from music_assistant_models.enums import DashboardType, EventType
from music_assistant_models.errors import ActionUnavailable, AuthenticationRequired

from homeassistant.components.music_assistant.const import (
    ATTR_CONF_EXPOSE_PLAYER_TO_HA,
    DASHBOARD_DEVICE_MODEL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .common import (
    setup_dashboards,
    setup_integration_from_fixtures,
    trigger_subscription_callback,
)

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    music_assistant_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test device removal."""
    assert await async_setup_component(hass, "config", {})
    await setup_integration_from_fixtures(hass, music_assistant_client)
    await hass.async_block_till_done()
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    client = await hass_ws_client(hass)

    # test if the removal should be denied if the device is still in use
    device_entry = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )[0]
    entity_id = "media_player.test_player_1"
    assert device_entry
    assert entity_registry.async_get(entity_id)
    assert hass.states.get(entity_id)
    music_assistant_client.config.remove_player_config = AsyncMock(
        side_effect=ActionUnavailable
    )
    response = await client.remove_device(device_entry.id)
    assert music_assistant_client.config.remove_player_config.call_count == 1
    assert response["success"] is False

    # test if the removal should be allowed if the device is not in use
    music_assistant_client.config.remove_player_config = AsyncMock()
    response = await client.remove_device(device_entry.id)
    assert response["success"] is True
    await hass.async_block_till_done()
    assert not device_registry.async_get(device_entry.id)
    assert not entity_registry.async_get(entity_id)
    assert not hass.states.get(entity_id)

    # test if the removal succeeds if its no longer provided by the server
    mass_player_id = "00:00:00:00:00:02"
    music_assistant_client.players._players.pop(mass_player_id)
    device_entry = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )[0]
    entity_id = "media_player.my_super_test_player_2"
    assert device_entry
    assert entity_registry.async_get(entity_id)
    assert hass.states.get(entity_id)
    music_assistant_client.config.remove_player_config = AsyncMock()
    response = await client.remove_device(device_entry.id)
    assert music_assistant_client.config.remove_player_config.call_count == 0
    assert response["success"] is True


async def test_remove_dashboard_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    music_assistant_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test dashboard device removal is refused while the endpoint is live."""
    assert await async_setup_component(hass, "config", {})
    setup_dashboards(music_assistant_client)
    config_entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    client = await hass_ws_client(hass)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "chromecast_kitchen_dashboard"), config_entry.entry_id
    )
    assert device_entry

    # the endpoint is still live - removal must be refused
    response = await client.remove_device(device_entry.id)
    assert response["success"] is False
    assert device_registry.async_get(device_entry.id)

    # the endpoint is gone from the server for good - removal is now allowed
    del music_assistant_client.dashboard._dashboards["chromecast_kitchen"]
    response = await client.remove_device(device_entry.id)
    assert response["success"] is True
    assert not device_registry.async_get(device_entry.id)

    # it comes back online later, without HA ever reloading in between -
    # its entity must not stay missing (regression for a "ghost" bug)
    music_assistant_client.dashboard._dashboards["chromecast_kitchen"] = (
        DashboardDevice(
            dashboard_id="chromecast_kitchen",
            name="Kitchen Display",
            supported_types={DashboardType.PARTY, DashboardType.NOW_PLAYING},
            provider_domain_hint="chromecast",
        )
    )
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.DASHBOARDS_UPDATED,
        data=[
            dashboard.to_dict()
            for dashboard in music_assistant_client.dashboard._dashboards.values()
        ],
    )
    assert hass.states.get("media_player.kitchen_display")


async def test_dashboard_device_survives_reload_with_empty_cache(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    music_assistant_client: MagicMock,
) -> None:
    """Test dashboard devices survive a reload with a momentarily empty cache.

    Regression test: dashboard registrations are connection-scoped, so right
    after an MA server restart + HA entry reload the dashboard cache can be
    empty before the physical endpoints have re-registered. The startup
    stale-device cleanup must not treat that as "gone for good".
    """
    setup_dashboards(music_assistant_client)
    config_entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "chromecast_kitchen_dashboard"), config_entry.entry_id
    )

    # simulate an MA server restart: the dashboard cache is empty again,
    # as if nothing had re-registered yet
    music_assistant_client.dashboard._dashboards = {}
    music_assistant_client.dashboard._sessions = {}
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "chromecast_kitchen_dashboard"), config_entry.entry_id
    )
    state = hass.states.get("media_player.kitchen_display")
    assert state
    assert state.state == "unavailable"


async def test_dashboard_device_id_namespaced(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    music_assistant_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a dashboard endpoint sharing a player's id gets its own device.

    Fully Kiosk registers dashboard_id == player_id. If the dashboard
    device identifier were not namespaced, the display would merge into
    the player's device, and removing the player would delete the display.
    """
    assert await async_setup_component(hass, "config", {})
    setup_dashboards(music_assistant_client)
    collision_id = "00:00:00:00:00:01"
    music_assistant_client.dashboard._dashboards[collision_id] = DashboardDevice(
        dashboard_id=collision_id,
        name="Player Display",
        supported_types={DashboardType.PARTY},
    )
    config_entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    client = await hass_ws_client(hass)

    player_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, collision_id), config_entry.entry_id
    )
    dashboard_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{collision_id}_dashboard"), config_entry.entry_id
    )
    assert player_device
    assert dashboard_device
    assert player_device.id != dashboard_device.id
    assert player_device.model != DASHBOARD_DEVICE_MODEL
    assert dashboard_device.model == DASHBOARD_DEVICE_MODEL

    # removing the player device must not be refused because a dashboard
    # endpoint happens to be live under the same bare id, and must not
    # touch the (separate) display device
    music_assistant_client.config.remove_player_config = AsyncMock()
    response = await client.remove_device(player_device.id)
    assert response["success"] is True
    await hass.async_block_till_done()
    assert not device_registry.async_get(player_device.id)
    assert device_registry.async_get(dashboard_device.id)


async def test_player_config_expose_to_ha_toggle(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    music_assistant_client: MagicMock,
) -> None:
    """Test player exposure toggle via config update."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    await hass.async_block_till_done()
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    # Initial state: player should be exposed (from fixture)
    entity_id = "media_player.test_player_1"
    player_id = "00:00:00:00:00:01"
    assert hass.states.get(entity_id)
    assert entity_registry.async_get(entity_id)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, player_id), config_entry.entry_id
    )
    assert device_entry
    assert player_id in config_entry.runtime_data.discovered_players

    # Simulate player config update: expose_to_ha = False
    # Trigger the subscription callback
    event_data = {
        "player_id": player_id,
        "provider": "test",
        "values": {
            ATTR_CONF_EXPOSE_PLAYER_TO_HA: {
                "key": ATTR_CONF_EXPOSE_PLAYER_TO_HA,
                "type": "boolean",
                "value": False,
                "label": ATTR_CONF_EXPOSE_PLAYER_TO_HA,
                "default_value": True,
            }
        },
    }
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.PLAYER_CONFIG_UPDATED,
        player_id,
        event_data,
    )

    # Verify player was removed from HA
    assert player_id not in config_entry.runtime_data.discovered_players
    assert not hass.states.get(entity_id)
    assert not entity_registry.async_get(entity_id)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, player_id), config_entry.entry_id
    )
    assert not device_entry

    # Now test re-adding the player: expose_to_ha = True
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.PLAYER_CONFIG_UPDATED,
        player_id,
        {
            "player_id": player_id,
            "provider": "test",
            "values": {
                ATTR_CONF_EXPOSE_PLAYER_TO_HA: {
                    "key": ATTR_CONF_EXPOSE_PLAYER_TO_HA,
                    "type": "boolean",
                    "value": True,
                    "label": ATTR_CONF_EXPOSE_PLAYER_TO_HA,
                    "default_value": True,
                }
            },
        },
    )

    # Verify player was re-added to HA
    assert player_id in config_entry.runtime_data.discovered_players
    assert hass.states.get(entity_id)
    assert entity_registry.async_get(entity_id)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, player_id), config_entry.entry_id
    )
    assert device_entry


async def test_authentication_required_triggers_reauth(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    music_assistant_client: MagicMock,
) -> None:
    """Test that AuthenticationRequired exception triggers reauth flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Assistant",
        data={"url": "http://localhost:8095", "token": "old_token"},
        unique_id="test_server_id",
    )
    config_entry.add_to_hass(hass)

    music_assistant_client.connect.side_effect = AuthenticationRequired(
        "Authentication required"
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    issue_id = f"config_entry_reauth_{DOMAIN}_{config_entry.entry_id}"
    assert issue_registry.async_get_issue("homeassistant", issue_id)


async def test_authentication_required_addon_no_reauth(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    music_assistant_client: MagicMock,
) -> None:
    """Test that AuthenticationRequired exception does not trigger reauth for addon."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Assistant",
        data={"url": "http://localhost:8095", "token": "old_token"},
        unique_id="test_server_id",
    )
    config_entry.add_to_hass(hass)

    music_assistant_client.server_info.homeassistant_addon = True

    music_assistant_client.connect.side_effect = AuthenticationRequired(
        "Authentication required"
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    issue_id = f"config_entry_reauth_{DOMAIN}_{config_entry.entry_id}"
    assert issue_registry.async_get_issue("homeassistant", issue_id) is None
