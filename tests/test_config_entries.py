"""Test the config manager."""
import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from tests.common import (
    MockModule, mock_coro, MockConfigEntry, async_fire_time_changed,
    MockPlatform, MockEntity, mock_integration, mock_entity_platform)


@pytest.fixture(autouse=True)
def mock_handlers():
    """Mock config flows."""
    class MockFlowHandler(config_entries.ConfigFlow):
        """Define a mock flow handler."""

        VERSION = 1

    with patch.dict(config_entries.HANDLERS, {
        'comp': MockFlowHandler,
        'test': MockFlowHandler,
    }):
        yield


@pytest.fixture
def manager(hass):
    """Fixture of a loaded config manager."""
    manager = config_entries.ConfigEntries(hass, {})
    manager._entries = []
    manager._store._async_ensure_stop_listener = lambda: None
    hass.config_entries = manager
    return manager


async def test_call_setup_entry(hass):
    """Test we call <component>.setup_entry."""
    entry = MockConfigEntry(domain='comp')
    entry.add_to_hass(hass)

    mock_setup_entry = MagicMock(return_value=mock_coro(True))
    mock_migrate_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(
        hass,
        MockModule('comp', async_setup_entry=mock_setup_entry,
                   async_migrate_entry=mock_migrate_entry))

    result = await async_setup_component(hass, 'comp', {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_LOADED


async def test_call_async_migrate_entry(hass):
    """Test we call <component>.async_migrate_entry when version mismatch."""
    entry = MockConfigEntry(domain='comp')
    entry.version = 2
    entry.add_to_hass(hass)

    mock_migrate_entry = MagicMock(return_value=mock_coro(True))
    mock_setup_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(
        hass,
        MockModule('comp', async_setup_entry=mock_setup_entry,
                   async_migrate_entry=mock_migrate_entry))

    result = await async_setup_component(hass, 'comp', {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_LOADED


async def test_call_async_migrate_entry_failure_false(hass):
    """Test migration fails if returns false."""
    entry = MockConfigEntry(domain='comp')
    entry.version = 2
    entry.add_to_hass(hass)

    mock_migrate_entry = MagicMock(return_value=mock_coro(False))
    mock_setup_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(
        hass,
        MockModule('comp', async_setup_entry=mock_setup_entry,
                   async_migrate_entry=mock_migrate_entry))

    result = await async_setup_component(hass, 'comp', {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state == config_entries.ENTRY_STATE_MIGRATION_ERROR


async def test_call_async_migrate_entry_failure_exception(hass):
    """Test migration fails if exception raised."""
    entry = MockConfigEntry(domain='comp')
    entry.version = 2
    entry.add_to_hass(hass)

    mock_migrate_entry = MagicMock(
        return_value=mock_coro(exception=Exception))
    mock_setup_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(
        hass,
        MockModule('comp', async_setup_entry=mock_setup_entry,
                   async_migrate_entry=mock_migrate_entry))

    result = await async_setup_component(hass, 'comp', {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state == config_entries.ENTRY_STATE_MIGRATION_ERROR


async def test_call_async_migrate_entry_failure_not_bool(hass):
    """Test migration fails if boolean not returned."""
    entry = MockConfigEntry(domain='comp')
    entry.version = 2
    entry.add_to_hass(hass)

    mock_migrate_entry = MagicMock(
        return_value=mock_coro())
    mock_setup_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(
        hass,
        MockModule('comp', async_setup_entry=mock_setup_entry,
                   async_migrate_entry=mock_migrate_entry))

    result = await async_setup_component(hass, 'comp', {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state == config_entries.ENTRY_STATE_MIGRATION_ERROR


async def test_call_async_migrate_entry_failure_not_supported(hass):
    """Test migration fails if async_migrate_entry not implemented."""
    entry = MockConfigEntry(domain='comp')
    entry.version = 2
    entry.add_to_hass(hass)

    mock_setup_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(
        hass,
        MockModule('comp', async_setup_entry=mock_setup_entry))

    result = await async_setup_component(hass, 'comp', {})
    assert result
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state == config_entries.ENTRY_STATE_MIGRATION_ERROR


async def test_remove_entry(hass, manager):
    """Test that we can remove an entry."""
    async def mock_setup_entry(hass, entry):
        """Mock setting up entry."""
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            entry, 'light'))
        return True

    async def mock_unload_entry(hass, entry):
        """Mock unloading an entry."""
        result = await hass.config_entries.async_forward_entry_unload(
            entry, 'light')
        assert result
        return result

    mock_remove_entry = MagicMock(
        side_effect=lambda *args, **kwargs: mock_coro())

    entity = MockEntity(
        unique_id='1234',
        name='Test Entity',
    )

    async def mock_setup_entry_platform(hass, entry, async_add_entities):
        """Mock setting up platform."""
        async_add_entities([entity])

    mock_integration(hass, MockModule(
        'test',
        async_setup_entry=mock_setup_entry,
        async_unload_entry=mock_unload_entry,
        async_remove_entry=mock_remove_entry
    ))
    mock_entity_platform(
        hass, 'light.test',
        MockPlatform(async_setup_entry=mock_setup_entry_platform))

    MockConfigEntry(
        domain='test_other', entry_id='test1'
    ).add_to_manager(manager)
    entry = MockConfigEntry(
        domain='test',
        entry_id='test2',
    )
    entry.add_to_manager(manager)
    MockConfigEntry(
        domain='test_other', entry_id='test3'
    ).add_to_manager(manager)

    # Check all config entries exist
    assert [item.entry_id for item in manager.async_entries()] == \
        ['test1', 'test2', 'test3']

    # Setup entry
    await entry.async_setup(hass)
    await hass.async_block_till_done()

    # Check entity state got added
    assert hass.states.get('light.test_entity') is not None
    # Group all_lights, light.test_entity
    assert len(hass.states.async_all()) == 2

    # Check entity got added to entity registry
    ent_reg = await hass.helpers.entity_registry.async_get_registry()
    assert len(ent_reg.entities) == 1
    entity_entry = list(ent_reg.entities.values())[0]
    assert entity_entry.config_entry_id == entry.entry_id

    # Remove entry
    result = await manager.async_remove('test2')
    await hass.async_block_till_done()

    # Check that unload went well and so no need to restart
    assert result == {
        'require_restart': False
    }

    # Check the remove callback was invoked.
    assert mock_remove_entry.call_count == 1

    # Check that config entry was removed.
    assert [item.entry_id for item in manager.async_entries()] == \
        ['test1', 'test3']

    # Check that entity state has been removed
    assert hass.states.get('light.test_entity') is None
    # Just Group all_lights
    assert len(hass.states.async_all()) == 1

    # Check that entity registry entry no longer references config_entry_id
    entity_entry = list(ent_reg.entities.values())[0]
    assert entity_entry.config_entry_id is None


async def test_remove_entry_handles_callback_error(hass, manager):
    """Test that exceptions in the remove callback are handled."""
    mock_setup_entry = MagicMock(return_value=mock_coro(True))
    mock_unload_entry = MagicMock(return_value=mock_coro(True))
    mock_remove_entry = MagicMock(
        side_effect=lambda *args, **kwargs: mock_coro())
    mock_integration(hass, MockModule(
        'test',
        async_setup_entry=mock_setup_entry,
        async_unload_entry=mock_unload_entry,
        async_remove_entry=mock_remove_entry
    ))
    entry = MockConfigEntry(
        domain='test',
        entry_id='test1',
    )
    entry.add_to_manager(manager)
    # Check all config entries exist
    assert [item.entry_id for item in manager.async_entries()] == \
        ['test1']
    # Setup entry
    await entry.async_setup(hass)
    await hass.async_block_till_done()

    # Remove entry
    result = await manager.async_remove('test1')
    await hass.async_block_till_done()
    # Check that unload went well and so no need to restart
    assert result == {
        'require_restart': False
    }
    # Check the remove callback was invoked.
    assert mock_remove_entry.call_count == 1
    # Check that config entry was removed.
    assert [item.entry_id for item in manager.async_entries()] == []


@asyncio.coroutine
def test_remove_entry_raises(hass, manager):
    """Test if a component raises while removing entry."""
    @asyncio.coroutine
    def mock_unload_entry(hass, entry):
        """Mock unload entry function."""
        raise Exception("BROKEN")

    mock_integration(hass, MockModule(
        'comp', async_unload_entry=mock_unload_entry))

    MockConfigEntry(domain='test', entry_id='test1').add_to_manager(manager)
    MockConfigEntry(
        domain='comp',
        entry_id='test2',
        state=config_entries.ENTRY_STATE_LOADED
    ).add_to_manager(manager)
    MockConfigEntry(domain='test', entry_id='test3').add_to_manager(manager)

    assert [item.entry_id for item in manager.async_entries()] == \
        ['test1', 'test2', 'test3']

    result = yield from manager.async_remove('test2')

    assert result == {
        'require_restart': True
    }
    assert [item.entry_id for item in manager.async_entries()] == \
        ['test1', 'test3']


@asyncio.coroutine
def test_remove_entry_if_not_loaded(hass, manager):
    """Test that we can remove an entry that is not loaded."""
    mock_unload_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(hass, MockModule(
        'comp', async_unload_entry=mock_unload_entry))

    MockConfigEntry(domain='test', entry_id='test1').add_to_manager(manager)
    MockConfigEntry(domain='comp', entry_id='test2').add_to_manager(manager)
    MockConfigEntry(domain='test', entry_id='test3').add_to_manager(manager)

    assert [item.entry_id for item in manager.async_entries()] == \
        ['test1', 'test2', 'test3']

    result = yield from manager.async_remove('test2')

    assert result == {
        'require_restart': False
    }
    assert [item.entry_id for item in manager.async_entries()] == \
        ['test1', 'test3']

    assert len(mock_unload_entry.mock_calls) == 0


@asyncio.coroutine
def test_add_entry_calls_setup_entry(hass, manager):
    """Test we call setup_config_entry."""
    mock_setup_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(
        hass,
        MockModule('comp', async_setup_entry=mock_setup_entry))

    class TestFlow(config_entries.ConfigFlow):

        VERSION = 1

        @asyncio.coroutine
        def async_step_user(self, user_input=None):
            return self.async_create_entry(
                title='title',
                data={
                    'token': 'supersecret'
                })

    with patch.dict(config_entries.HANDLERS, {'comp': TestFlow, 'beer': 5}):
        yield from manager.flow.async_init(
            'comp', context={'source': config_entries.SOURCE_USER})
        yield from hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry = mock_setup_entry.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry.data == {
        'token': 'supersecret'
    }


@asyncio.coroutine
def test_entries_gets_entries(manager):
    """Test entries are filtered by domain."""
    MockConfigEntry(domain='test').add_to_manager(manager)
    entry1 = MockConfigEntry(domain='test2')
    entry1.add_to_manager(manager)
    entry2 = MockConfigEntry(domain='test2')
    entry2.add_to_manager(manager)

    assert manager.async_entries('test2') == [entry1, entry2]


@asyncio.coroutine
def test_domains_gets_uniques(manager):
    """Test we only return each domain once."""
    MockConfigEntry(domain='test').add_to_manager(manager)
    MockConfigEntry(domain='test2').add_to_manager(manager)
    MockConfigEntry(domain='test2').add_to_manager(manager)
    MockConfigEntry(domain='test').add_to_manager(manager)
    MockConfigEntry(domain='test3').add_to_manager(manager)

    assert manager.async_domains() == ['test', 'test2', 'test3']


async def test_saving_and_loading(hass):
    """Test that we're saving and loading correctly."""
    mock_integration(hass, MockModule(
        'test', async_setup_entry=lambda *args: mock_coro(True)))

    class TestFlow(config_entries.ConfigFlow):
        VERSION = 5
        CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

        @asyncio.coroutine
        def async_step_user(self, user_input=None):
            return self.async_create_entry(
                title='Test Title',
                data={
                    'token': 'abcd'
                }
            )

    with patch.dict(config_entries.HANDLERS, {'test': TestFlow}):
        await hass.config_entries.flow.async_init(
            'test', context={'source': config_entries.SOURCE_USER})

    class Test2Flow(config_entries.ConfigFlow):
        VERSION = 3
        CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

        @asyncio.coroutine
        def async_step_user(self, user_input=None):
            return self.async_create_entry(
                title='Test 2 Title',
                data={
                    'username': 'bla'
                }
            )

    with patch('homeassistant.config_entries.HANDLERS.get',
               return_value=Test2Flow):
        await hass.config_entries.flow.async_init(
            'test', context={'source': config_entries.SOURCE_USER})

    # To trigger the call_later
    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=1))
    # To execute the save
    await hass.async_block_till_done()

    # Now load written data in new config manager
    manager = config_entries.ConfigEntries(hass, {})
    await manager.async_initialize()

    # Ensure same order
    for orig, loaded in zip(hass.config_entries.async_entries(),
                            manager.async_entries()):
        assert orig.version == loaded.version
        assert orig.domain == loaded.domain
        assert orig.title == loaded.title
        assert orig.data == loaded.data
        assert orig.source == loaded.source
        assert orig.connection_class == loaded.connection_class


async def test_forward_entry_sets_up_component(hass):
    """Test we setup the component entry is forwarded to."""
    entry = MockConfigEntry(domain='original')

    mock_original_setup_entry = MagicMock(return_value=mock_coro(True))
    mock_integration(
        hass,
        MockModule('original', async_setup_entry=mock_original_setup_entry))

    mock_forwarded_setup_entry = MagicMock(return_value=mock_coro(True))
    mock_integration(
        hass,
        MockModule('forwarded', async_setup_entry=mock_forwarded_setup_entry))

    await hass.config_entries.async_forward_entry_setup(entry, 'forwarded')
    assert len(mock_original_setup_entry.mock_calls) == 0
    assert len(mock_forwarded_setup_entry.mock_calls) == 1


async def test_forward_entry_does_not_setup_entry_if_setup_fails(hass):
    """Test we do not set up entry if component setup fails."""
    entry = MockConfigEntry(domain='original')

    mock_setup = MagicMock(return_value=mock_coro(False))
    mock_setup_entry = MagicMock()
    mock_integration(hass, MockModule(
        'forwarded',
        async_setup=mock_setup,
        async_setup_entry=mock_setup_entry,
    ))

    await hass.config_entries.async_forward_entry_setup(entry, 'forwarded')
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0


async def test_discovery_notification(hass):
    """Test that we create/dismiss a notification when source is discovery."""
    mock_integration(hass, MockModule('test'))
    await async_setup_component(hass, 'persistent_notification', {})

    class TestFlow(config_entries.ConfigFlow):
        VERSION = 5

        async def async_step_discovery(self, user_input=None):
            if user_input is not None:
                return self.async_create_entry(
                    title='Test Title',
                    data={
                        'token': 'abcd'
                    }
                )
            return self.async_show_form(
                step_id='discovery',
            )

    with patch.dict(config_entries.HANDLERS, {'test': TestFlow}):
        result = await hass.config_entries.flow.async_init(
            'test', context={'source': config_entries.SOURCE_DISCOVERY})

    await hass.async_block_till_done()
    state = hass.states.get('persistent_notification.config_entry_discovery')
    assert state is not None

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()
    state = hass.states.get('persistent_notification.config_entry_discovery')
    assert state is None


async def test_discovery_notification_not_created(hass):
    """Test that we not create a notification when discovery is aborted."""
    mock_integration(hass, MockModule('test'))
    await async_setup_component(hass, 'persistent_notification', {})

    class TestFlow(config_entries.ConfigFlow):
        VERSION = 5

        async def async_step_discovery(self, user_input=None):
            return self.async_abort(reason='test')

    with patch.dict(config_entries.HANDLERS, {'test': TestFlow}):
        await hass.config_entries.flow.async_init(
            'test', context={'source': config_entries.SOURCE_DISCOVERY})

    await hass.async_block_till_done()
    state = hass.states.get('persistent_notification.config_entry_discovery')
    assert state is None


async def test_loading_default_config(hass):
    """Test loading the default config."""
    manager = config_entries.ConfigEntries(hass, {})

    with patch('homeassistant.util.json.open', side_effect=FileNotFoundError):
        await manager.async_initialize()

    assert len(manager.async_entries()) == 0


async def test_updating_entry_data(manager):
    """Test that we can update an entry data."""
    entry = MockConfigEntry(
        domain='test',
        data={'first': True},
        state=config_entries.ENTRY_STATE_SETUP_ERROR,
    )
    entry.add_to_manager(manager)

    manager.async_update_entry(entry)
    assert entry.data == {
        'first': True
    }

    manager.async_update_entry(entry, data={
        'second': True
    })
    assert entry.data == {
        'second': True
    }


async def test_update_entry_options_and_trigger_listener(hass, manager):
    """Test that we can update entry options and trigger listener."""
    entry = MockConfigEntry(
        domain='test',
        options={'first': True},
    )
    entry.add_to_manager(manager)

    async def update_listener(hass, entry):
        """Test function."""
        assert entry.options == {
            'second': True
        }

    entry.add_update_listener(update_listener)

    manager.async_update_entry(entry, options={
        'second': True
    })

    assert entry.options == {
        'second': True
    }


async def test_setup_raise_not_ready(hass, caplog):
    """Test a setup raising not ready."""
    entry = MockConfigEntry(domain='test')

    mock_setup_entry = MagicMock(side_effect=ConfigEntryNotReady)
    mock_integration(
        hass, MockModule('test', async_setup_entry=mock_setup_entry))

    with patch('homeassistant.helpers.event.async_call_later') as mock_call:
        await entry.async_setup(hass)

    assert len(mock_call.mock_calls) == 1
    assert 'Config entry for test not ready yet' in caplog.text
    p_hass, p_wait_time, p_setup = mock_call.mock_calls[0][1]

    assert p_hass is hass
    assert p_wait_time == 5
    assert entry.state == config_entries.ENTRY_STATE_SETUP_RETRY

    mock_setup_entry.side_effect = None
    mock_setup_entry.return_value = mock_coro(True)

    await p_setup(None)
    assert entry.state == config_entries.ENTRY_STATE_LOADED


async def test_setup_retrying_during_unload(hass):
    """Test if we unload an entry that is in retry mode."""
    entry = MockConfigEntry(domain='test')

    mock_setup_entry = MagicMock(side_effect=ConfigEntryNotReady)
    mock_integration(
        hass, MockModule('test', async_setup_entry=mock_setup_entry))

    with patch('homeassistant.helpers.event.async_call_later') as mock_call:
        await entry.async_setup(hass)

    assert entry.state == config_entries.ENTRY_STATE_SETUP_RETRY
    assert len(mock_call.return_value.mock_calls) == 0

    await entry.async_unload(hass)

    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
    assert len(mock_call.return_value.mock_calls) == 1


async def test_entry_options(hass, manager):
    """Test that we can set options on an entry."""
    entry = MockConfigEntry(
        domain='test',
        data={'first': True},
        options=None
    )
    entry.add_to_manager(manager)

    class TestFlow:
        @staticmethod
        @callback
        def async_get_options_flow(config, options):
            class OptionsFlowHandler(data_entry_flow.FlowHandler):
                def __init__(self, config, options):
                    pass
            return OptionsFlowHandler(config, options)

    config_entries.HANDLERS['test'] = TestFlow()
    flow = await manager.options._async_create_flow(
        entry.entry_id, context={'source': 'test'}, data=None)

    flow.handler = entry.entry_id  # Used to keep reference to config entry

    await manager.options._async_finish_flow(
        flow, {'data': {'second': True}})

    assert entry.data == {
        'first': True
    }

    assert entry.options == {
        'second': True
    }


async def test_entry_setup_succeed(hass, manager):
    """Test that we can setup an entry."""
    entry = MockConfigEntry(
        domain='comp',
        state=config_entries.ENTRY_STATE_NOT_LOADED
    )
    entry.add_to_hass(hass)

    mock_setup = MagicMock(return_value=mock_coro(True))
    mock_setup_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(hass, MockModule(
        'comp',
        async_setup=mock_setup,
        async_setup_entry=mock_setup_entry
    ))

    assert await manager.async_setup(entry.entry_id)
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_LOADED


@pytest.mark.parametrize('state', (
    config_entries.ENTRY_STATE_LOADED,
    config_entries.ENTRY_STATE_SETUP_ERROR,
    config_entries.ENTRY_STATE_MIGRATION_ERROR,
    config_entries.ENTRY_STATE_SETUP_RETRY,
    config_entries.ENTRY_STATE_FAILED_UNLOAD,
))
async def test_entry_setup_invalid_state(hass, manager, state):
    """Test that we cannot setup an entry with invalid state."""
    entry = MockConfigEntry(
        domain='comp',
        state=state
    )
    entry.add_to_hass(hass)

    mock_setup = MagicMock(return_value=mock_coro(True))
    mock_setup_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(hass, MockModule(
        'comp',
        async_setup=mock_setup,
        async_setup_entry=mock_setup_entry
    ))

    with pytest.raises(config_entries.OperationNotAllowed):
        assert await manager.async_setup(entry.entry_id)

    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state == state


async def test_entry_unload_succeed(hass, manager):
    """Test that we can unload an entry."""
    entry = MockConfigEntry(
        domain='comp',
        state=config_entries.ENTRY_STATE_LOADED
    )
    entry.add_to_hass(hass)

    async_unload_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(hass, MockModule(
        'comp',
        async_unload_entry=async_unload_entry
    ))

    assert await manager.async_unload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED


@pytest.mark.parametrize('state', (
    config_entries.ENTRY_STATE_NOT_LOADED,
    config_entries.ENTRY_STATE_SETUP_ERROR,
    config_entries.ENTRY_STATE_SETUP_RETRY,
))
async def test_entry_unload_failed_to_load(hass, manager, state):
    """Test that we can unload an entry."""
    entry = MockConfigEntry(
        domain='comp',
        state=state,
    )
    entry.add_to_hass(hass)

    async_unload_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(hass, MockModule(
        'comp',
        async_unload_entry=async_unload_entry
    ))

    assert await manager.async_unload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 0
    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED


@pytest.mark.parametrize('state', (
    config_entries.ENTRY_STATE_MIGRATION_ERROR,
    config_entries.ENTRY_STATE_FAILED_UNLOAD,
))
async def test_entry_unload_invalid_state(hass, manager, state):
    """Test that we cannot unload an entry with invalid state."""
    entry = MockConfigEntry(
        domain='comp',
        state=state
    )
    entry.add_to_hass(hass)

    async_unload_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(hass, MockModule(
        'comp',
        async_unload_entry=async_unload_entry
    ))

    with pytest.raises(config_entries.OperationNotAllowed):
        assert await manager.async_unload(entry.entry_id)

    assert len(async_unload_entry.mock_calls) == 0
    assert entry.state == state


async def test_entry_reload_succeed(hass, manager):
    """Test that we can reload an entry."""
    entry = MockConfigEntry(
        domain='comp',
        state=config_entries.ENTRY_STATE_LOADED
    )
    entry.add_to_hass(hass)

    async_setup = MagicMock(return_value=mock_coro(True))
    async_setup_entry = MagicMock(return_value=mock_coro(True))
    async_unload_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(hass, MockModule(
        'comp',
        async_setup=async_setup,
        async_setup_entry=async_setup_entry,
        async_unload_entry=async_unload_entry
    ))

    assert await manager.async_reload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 1
    assert len(async_setup.mock_calls) == 1
    assert len(async_setup_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_LOADED


@pytest.mark.parametrize('state', (
    config_entries.ENTRY_STATE_NOT_LOADED,
    config_entries.ENTRY_STATE_SETUP_ERROR,
    config_entries.ENTRY_STATE_SETUP_RETRY,
))
async def test_entry_reload_not_loaded(hass, manager, state):
    """Test that we can reload an entry."""
    entry = MockConfigEntry(
        domain='comp',
        state=state
    )
    entry.add_to_hass(hass)

    async_setup = MagicMock(return_value=mock_coro(True))
    async_setup_entry = MagicMock(return_value=mock_coro(True))
    async_unload_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(hass, MockModule(
        'comp',
        async_setup=async_setup,
        async_setup_entry=async_setup_entry,
        async_unload_entry=async_unload_entry
    ))

    assert await manager.async_reload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 0
    assert len(async_setup.mock_calls) == 1
    assert len(async_setup_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_LOADED


@pytest.mark.parametrize('state', (
    config_entries.ENTRY_STATE_MIGRATION_ERROR,
    config_entries.ENTRY_STATE_FAILED_UNLOAD,
))
async def test_entry_reload_error(hass, manager, state):
    """Test that we can reload an entry."""
    entry = MockConfigEntry(
        domain='comp',
        state=state
    )
    entry.add_to_hass(hass)

    async_setup = MagicMock(return_value=mock_coro(True))
    async_setup_entry = MagicMock(return_value=mock_coro(True))
    async_unload_entry = MagicMock(return_value=mock_coro(True))

    mock_integration(hass, MockModule(
        'comp',
        async_setup=async_setup,
        async_setup_entry=async_setup_entry,
        async_unload_entry=async_unload_entry
    ))

    with pytest.raises(config_entries.OperationNotAllowed):
        assert await manager.async_reload(entry.entry_id)

    assert len(async_unload_entry.mock_calls) == 0
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 0

    assert entry.state == state
