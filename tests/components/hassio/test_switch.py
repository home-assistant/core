"""The tests for the hassio switch."""

from collections.abc import AsyncGenerator
from dataclasses import replace
import os
from unittest.mock import AsyncMock, Mock, patch

from aiohasupervisor.models import AddonState, InstalledAddonComplete
import pytest

from homeassistant.components.hassio import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import MOCK_REPOSITORIES, MOCK_STORE_ADDONS

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the hassio integration and enable entity."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
        await hass.async_block_till_done()

        yield config_entry


async def enable_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Enable an entity and reload the config entry."""
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
def mock_all(
    aioclient_mock: AiohttpClientMocker,
    addon_installed: AsyncMock,
    store_info: AsyncMock,
    addon_changelog: AsyncMock,
    addon_stats: AsyncMock,
    resolution_info: AsyncMock,
    jobs_info: AsyncMock,
    host_info: AsyncMock,
    supervisor_root_info: AsyncMock,
    homeassistant_info: AsyncMock,
    supervisor_info: AsyncMock,
    addons_list: AsyncMock,
    network_info: AsyncMock,
    os_info: AsyncMock,
    homeassistant_stats: AsyncMock,
    supervisor_stats: AsyncMock,
) -> None:
    """Mock all setup requests."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )
    addons_list.return_value[1] = replace(
        addons_list.return_value[1], name="test-two", slug="test-two"
    )

    def mock_addon_info(slug: str):
        addon = Mock(
            spec=InstalledAddonComplete,
            to_dict=addon_installed.return_value.to_dict,
            **addon_installed.return_value.to_dict(),
        )
        if slug == "test":
            addon.name = "test"
            addon.slug = "test"
            addon.version = "2.0.0"
            addon.version_latest = "2.0.1"
            addon.update_available = True
            addon.state = AddonState.STARTED
            addon.url = "https://github.com/home-assistant/addons/test"
            addon.auto_update = True
        else:
            addon.name = "test-two"
            addon.slug = "test-two"
            addon.version = "3.1.0"
            addon.version_latest = "3.1.0"
            addon.update_available = False
            addon.state = AddonState.STOPPED
            addon.url = "https://github.com"
            addon.auto_update = False

        return addon

    addon_installed.side_effect = mock_addon_info


@pytest.mark.parametrize(
    ("store_addons", "store_repositories"), [(MOCK_STORE_ADDONS, MOCK_REPOSITORIES)]
)
@pytest.mark.parametrize(
    ("entity_id", "expected", "addon_state"),
    [
        ("switch.test", "on", "started"),
        ("switch.test_two", "off", "stopped"),
    ],
)
async def test_switch_state(
    hass: HomeAssistant,
    entity_id: str,
    expected: str,
    addon_state: str,
    entity_registry: er.EntityRegistry,
    addon_installed: AsyncMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test hassio addon switch state."""
    addon_installed.return_value.state = addon_state

    # Verify that the entity is disabled by default.
    assert hass.states.get(entity_id) is None

    # Enable the entity.
    await enable_entity(hass, entity_registry, setup_integration, entity_id)

    # Verify that the entity have the expected state.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("store_addons", "store_repositories"), [(MOCK_STORE_ADDONS, MOCK_REPOSITORIES)]
)
async def test_switch_turn_on(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    addon_installed: AsyncMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test turning on addon switch."""
    entity_id = "switch.test_two"
    addon_installed.return_value.state = "stopped"

    # Mock the start addon API call
    aioclient_mock.post("http://127.0.0.1/addons/test-two/start", json={"result": "ok"})

    # Verify that the entity is disabled by default.
    assert hass.states.get(entity_id) is None

    # Enable the entity.
    await enable_entity(hass, entity_registry, setup_integration, entity_id)

    # Verify initial state is off
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    # Turn on the switch
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    # Verify the API was called
    assert aioclient_mock.mock_calls[-1][1].path == "/addons/test-two/start"
    assert aioclient_mock.mock_calls[-1][0] == "POST"


@pytest.mark.parametrize(
    ("store_addons", "store_repositories"), [(MOCK_STORE_ADDONS, MOCK_REPOSITORIES)]
)
async def test_switch_turn_off(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    addon_installed: AsyncMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test turning off addon switch."""
    entity_id = "switch.test"
    addon_installed.return_value.state = "started"

    # Mock the stop addon API call
    aioclient_mock.post("http://127.0.0.1/addons/test/stop", json={"result": "ok"})

    # Verify that the entity is disabled by default.
    assert hass.states.get(entity_id) is None

    # Enable the entity.
    await enable_entity(hass, entity_registry, setup_integration, entity_id)

    # Verify initial state is on
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Turn off the switch
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    # Verify the API was called
    assert aioclient_mock.mock_calls[-1][1].path == "/addons/test/stop"
    assert aioclient_mock.mock_calls[-1][0] == "POST"
