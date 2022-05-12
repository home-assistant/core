"""The tests for the Entity component helper."""
# pylint: disable=protected-access
from collections import OrderedDict
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, Mock, patch

from freezegun import freeze_time
import pytest
import voluptuous as vol

from homeassistant.const import (
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.core as ha
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import discovery
from homeassistant.helpers.entity_component import EntityComponent, async_update_entity
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockModule,
    MockPlatform,
    async_fire_time_changed,
    mock_entity_platform,
    mock_integration,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "test_domain"


async def test_setup_loads_platforms(hass):
    """Test the loading of the platforms."""
    component_setup = Mock(return_value=True)
    platform_setup = Mock(return_value=None)

    mock_integration(hass, MockModule("test_component", setup=component_setup))
    # mock the dependencies
    mock_integration(hass, MockModule("mod2", dependencies=["test_component"]))
    mock_entity_platform(hass, "test_domain.mod2", MockPlatform(platform_setup))

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    assert not component_setup.called
    assert not platform_setup.called

    component.setup({DOMAIN: {"platform": "mod2"}})

    await hass.async_block_till_done()
    assert component_setup.called
    assert platform_setup.called


async def test_setup_recovers_when_setup_raises(hass):
    """Test the setup if exceptions are happening."""
    platform1_setup = Mock(side_effect=Exception("Broken"))
    platform2_setup = Mock(return_value=None)

    mock_entity_platform(hass, "test_domain.mod1", MockPlatform(platform1_setup))
    mock_entity_platform(hass, "test_domain.mod2", MockPlatform(platform2_setup))

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    assert not platform1_setup.called
    assert not platform2_setup.called

    component.setup(
        OrderedDict(
            [
                (DOMAIN, {"platform": "mod1"}),
                (f"{DOMAIN} 2", {"platform": "non_exist"}),
                (f"{DOMAIN} 3", {"platform": "mod2"}),
            ]
        )
    )

    await hass.async_block_till_done()
    assert platform1_setup.called
    assert platform2_setup.called


@patch(
    "homeassistant.helpers.entity_component.EntityComponent.async_setup_platform",
)
@patch("homeassistant.setup.async_setup_component", return_value=True)
async def test_setup_does_discovery(mock_setup_component, mock_setup, hass):
    """Test setup for discovery."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    component.setup({})

    discovery.load_platform(
        hass, DOMAIN, "platform_test", {"msg": "discovery_info"}, {DOMAIN: {}}
    )

    await hass.async_block_till_done()

    assert mock_setup.called
    assert ("platform_test", {}, {"msg": "discovery_info"}) == mock_setup.call_args[0]


@patch("homeassistant.helpers.entity_platform.async_track_time_interval")
async def test_set_scan_interval_via_config(mock_track, hass):
    """Test the setting of the scan interval via configuration."""

    def platform_setup(hass, config, add_entities, discovery_info=None):
        """Test the platform setup."""
        add_entities([MockEntity(should_poll=True)])

    mock_entity_platform(hass, "test_domain.platform", MockPlatform(platform_setup))

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    component.setup(
        {DOMAIN: {"platform": "platform", "scan_interval": timedelta(seconds=30)}}
    )

    await hass.async_block_till_done()
    assert mock_track.called
    assert timedelta(seconds=30) == mock_track.call_args[0][2]


async def test_set_entity_namespace_via_config(hass):
    """Test setting an entity namespace."""

    def platform_setup(hass, config, add_entities, discovery_info=None):
        """Test the platform setup."""
        add_entities([MockEntity(name="beer"), MockEntity(name=None)])

    platform = MockPlatform(platform_setup)

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    component.setup({DOMAIN: {"platform": "platform", "entity_namespace": "yummy"}})

    await hass.async_block_till_done()

    assert sorted(hass.states.async_entity_ids()) == [
        "test_domain.yummy_beer",
        "test_domain.yummy_unnamed_device",
    ]


async def test_extract_from_service_available_device(hass):
    """Test the extraction of entity from service and device is available."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_add_entities(
        [
            MockEntity(name="test_1"),
            MockEntity(name="test_2", available=False),
            MockEntity(name="test_3"),
            MockEntity(name="test_4", available=False),
        ]
    )

    call_1 = ha.ServiceCall("test", "service", data={"entity_id": ENTITY_MATCH_ALL})

    assert ["test_domain.test_1", "test_domain.test_3"] == sorted(
        ent.entity_id for ent in (await component.async_extract_from_service(call_1))
    )

    call_2 = ha.ServiceCall(
        "test",
        "service",
        data={"entity_id": ["test_domain.test_3", "test_domain.test_4"]},
    )

    assert ["test_domain.test_3"] == sorted(
        ent.entity_id for ent in (await component.async_extract_from_service(call_2))
    )


async def test_platform_not_ready(hass):
    """Test that we retry when platform not ready."""
    platform1_setup = Mock(side_effect=[PlatformNotReady, PlatformNotReady, None])
    mock_integration(hass, MockModule("mod1"))
    mock_entity_platform(hass, "test_domain.mod1", MockPlatform(platform1_setup))

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_setup({DOMAIN: {"platform": "mod1"}})
    await hass.async_block_till_done()
    assert len(platform1_setup.mock_calls) == 1
    assert "test_domain.mod1" not in hass.config.components

    utcnow = dt_util.utcnow()

    with freeze_time(utcnow):
        # Should not trigger attempt 2
        async_fire_time_changed(hass, utcnow + timedelta(seconds=29))
        await hass.async_block_till_done()
        assert len(platform1_setup.mock_calls) == 1

        # Should trigger attempt 2
        async_fire_time_changed(hass, utcnow + timedelta(seconds=30))
        await hass.async_block_till_done()
        assert len(platform1_setup.mock_calls) == 2
        assert "test_domain.mod1" not in hass.config.components

        # This should not trigger attempt 3
        async_fire_time_changed(hass, utcnow + timedelta(seconds=59))
        await hass.async_block_till_done()
        assert len(platform1_setup.mock_calls) == 2

        # Trigger attempt 3, which succeeds
        async_fire_time_changed(hass, utcnow + timedelta(seconds=60))
        await hass.async_block_till_done()
        assert len(platform1_setup.mock_calls) == 3
        assert "test_domain.mod1" in hass.config.components


async def test_extract_from_service_fails_if_no_entity_id(hass):
    """Test the extraction of everything from service."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_add_entities(
        [MockEntity(name="test_1"), MockEntity(name="test_2")]
    )

    assert (
        await component.async_extract_from_service(ha.ServiceCall("test", "service"))
        == []
    )
    assert (
        await component.async_extract_from_service(
            ha.ServiceCall("test", "service", {"entity_id": ENTITY_MATCH_NONE})
        )
        == []
    )
    assert (
        await component.async_extract_from_service(
            ha.ServiceCall("test", "service", {"area_id": ENTITY_MATCH_NONE})
        )
        == []
    )


async def test_extract_from_service_filter_out_non_existing_entities(hass):
    """Test the extraction of non existing entities from service."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_add_entities(
        [MockEntity(name="test_1"), MockEntity(name="test_2")]
    )

    call = ha.ServiceCall(
        "test",
        "service",
        {"entity_id": ["test_domain.test_2", "test_domain.non_exist"]},
    )

    assert ["test_domain.test_2"] == [
        ent.entity_id for ent in await component.async_extract_from_service(call)
    ]


async def test_extract_from_service_no_group_expand(hass):
    """Test not expanding a group."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_add_entities([MockEntity(entity_id="group.test_group")])

    call = ha.ServiceCall("test", "service", {"entity_id": ["group.test_group"]})

    extracted = await component.async_extract_from_service(call, expand_group=False)
    assert len(extracted) == 1
    assert extracted[0].entity_id == "group.test_group"


async def test_setup_dependencies_platform(hass):
    """Test we setup the dependencies of a platform.

    We're explicitly testing that we process dependencies even if a component
    with the same name has already been loaded.
    """
    mock_integration(
        hass, MockModule("test_component", dependencies=["test_component2"])
    )
    mock_integration(hass, MockModule("test_component2"))
    mock_entity_platform(hass, "test_domain.test_component", MockPlatform())

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_setup({DOMAIN: {"platform": "test_component"}})
    await hass.async_block_till_done()
    assert "test_component" in hass.config.components
    assert "test_component2" in hass.config.components
    assert "test_domain.test_component" in hass.config.components


async def test_setup_entry(hass):
    """Test setup entry calls async_setup_entry on platform."""
    mock_setup_entry = AsyncMock(return_value=True)
    mock_entity_platform(
        hass,
        "test_domain.entry_domain",
        MockPlatform(
            async_setup_entry=mock_setup_entry, scan_interval=timedelta(seconds=5)
        ),
    )

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entry = MockConfigEntry(domain="entry_domain")

    assert await component.async_setup_entry(entry)
    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry, _ = mock_setup_entry.mock_calls[0][1]
    assert p_hass is hass
    assert p_entry is entry

    assert component._platforms[entry.entry_id].scan_interval == timedelta(seconds=5)


async def test_setup_entry_platform_not_exist(hass):
    """Test setup entry fails if platform does not exist."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entry = MockConfigEntry(domain="non_existing")

    assert (await component.async_setup_entry(entry)) is False


async def test_setup_entry_fails_duplicate(hass):
    """Test we don't allow setting up a config entry twice."""
    mock_setup_entry = AsyncMock(return_value=True)
    mock_entity_platform(
        hass,
        "test_domain.entry_domain",
        MockPlatform(async_setup_entry=mock_setup_entry),
    )

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entry = MockConfigEntry(domain="entry_domain")

    assert await component.async_setup_entry(entry)

    with pytest.raises(ValueError):
        await component.async_setup_entry(entry)


async def test_unload_entry_resets_platform(hass):
    """Test unloading an entry removes all entities."""
    mock_setup_entry = AsyncMock(return_value=True)
    mock_entity_platform(
        hass,
        "test_domain.entry_domain",
        MockPlatform(async_setup_entry=mock_setup_entry),
    )

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entry = MockConfigEntry(domain="entry_domain")

    assert await component.async_setup_entry(entry)
    assert len(mock_setup_entry.mock_calls) == 1
    add_entities = mock_setup_entry.mock_calls[0][1][2]
    add_entities([MockEntity()])
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    assert await component.async_unload_entry(entry)
    assert len(hass.states.async_entity_ids()) == 0


async def test_unload_entry_fails_if_never_loaded(hass):
    """."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entry = MockConfigEntry(domain="entry_domain")

    with pytest.raises(ValueError):
        await component.async_unload_entry(entry)


async def test_update_entity(hass):
    """Test that we can update an entity with the helper."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entity = MockEntity()
    entity.async_write_ha_state = Mock()
    entity.async_update_ha_state = AsyncMock(return_value=None)
    await component.async_add_entities([entity])

    # Called as part of async_add_entities
    assert len(entity.async_write_ha_state.mock_calls) == 1

    await async_update_entity(hass, entity.entity_id)

    assert len(entity.async_update_ha_state.mock_calls) == 1
    assert entity.async_update_ha_state.mock_calls[-1][1][0] is True


async def test_set_service_race(hass):
    """Test race condition on setting service."""
    exception = False

    def async_loop_exception_handler(_, _2) -> None:
        """Handle all exception inside the core loop."""
        nonlocal exception
        exception = True

    hass.loop.set_exception_handler(async_loop_exception_handler)

    await async_setup_component(hass, "group", {})
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    for _ in range(2):
        hass.async_create_task(component.async_add_entities([MockEntity()]))

    await hass.async_block_till_done()
    assert not exception


async def test_extract_all_omit_entity_id(hass, caplog):
    """Test extract all with None and *."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_add_entities(
        [MockEntity(name="test_1"), MockEntity(name="test_2")]
    )

    call = ha.ServiceCall("test", "service")

    assert [] == sorted(
        ent.entity_id for ent in await component.async_extract_from_service(call)
    )


async def test_extract_all_use_match_all(hass, caplog):
    """Test extract all with None and *."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_add_entities(
        [MockEntity(name="test_1"), MockEntity(name="test_2")]
    )

    call = ha.ServiceCall("test", "service", {"entity_id": "all"})

    assert ["test_domain.test_1", "test_domain.test_2"] == sorted(
        ent.entity_id for ent in await component.async_extract_from_service(call)
    )
    assert (
        "Not passing an entity ID to a service to target all entities is deprecated"
    ) not in caplog.text


async def test_register_entity_service(hass):
    """Test not expanding a group."""
    entity = MockEntity(entity_id=f"{DOMAIN}.entity")
    calls = []

    @ha.callback
    def appender(**kwargs):
        calls.append(kwargs)

    entity.async_called_by_service = appender

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_add_entities([entity])

    component.async_register_entity_service(
        "hello", {"some": str}, "async_called_by_service"
    )

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "hello",
            {"entity_id": entity.entity_id, "invalid": "data"},
            blocking=True,
        )
        assert len(calls) == 0

    await hass.services.async_call(
        DOMAIN, "hello", {"entity_id": entity.entity_id, "some": "data"}, blocking=True
    )
    assert len(calls) == 1
    assert calls[0] == {"some": "data"}

    await hass.services.async_call(
        DOMAIN, "hello", {"entity_id": ENTITY_MATCH_ALL, "some": "data"}, blocking=True
    )
    assert len(calls) == 2
    assert calls[1] == {"some": "data"}

    await hass.services.async_call(
        DOMAIN, "hello", {"entity_id": ENTITY_MATCH_NONE, "some": "data"}, blocking=True
    )
    assert len(calls) == 2

    await hass.services.async_call(
        DOMAIN, "hello", {"area_id": ENTITY_MATCH_NONE, "some": "data"}, blocking=True
    )
    assert len(calls) == 2


async def test_platforms_shutdown_on_stop(hass):
    """Test that we shutdown platforms on stop."""
    platform1_setup = Mock(side_effect=[PlatformNotReady, PlatformNotReady, None])
    mock_integration(hass, MockModule("mod1"))
    mock_entity_platform(hass, "test_domain.mod1", MockPlatform(platform1_setup))

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_setup({DOMAIN: {"platform": "mod1"}})
    await hass.async_block_till_done()
    assert len(platform1_setup.mock_calls) == 1
    assert "test_domain.mod1" not in hass.config.components

    with patch.object(
        component._platforms[DOMAIN], "async_shutdown"
    ) as mock_async_shutdown:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert mock_async_shutdown.called
