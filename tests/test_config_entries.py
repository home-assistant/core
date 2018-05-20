"""Test the config manager."""
import asyncio
from unittest.mock import MagicMock, patch, mock_open

import pytest

from homeassistant import config_entries, loader, data_entry_flow
from homeassistant.setup import async_setup_component

from tests.common import MockModule, mock_coro, MockConfigEntry


@pytest.fixture
def manager(hass):
    """Fixture of a loaded config manager."""
    manager = config_entries.ConfigEntries(hass, {})
    manager._entries = []
    hass.config_entries = manager
    return manager


@asyncio.coroutine
def test_call_setup_entry(hass):
    """Test we call <component>.setup_entry."""
    MockConfigEntry(domain='comp').add_to_hass(hass)

    mock_setup_entry = MagicMock(return_value=mock_coro(True))

    loader.set_component(
        hass, 'comp',
        MockModule('comp', async_setup_entry=mock_setup_entry))

    result = yield from async_setup_component(hass, 'comp', {})
    assert result
    assert len(mock_setup_entry.mock_calls) == 1


@asyncio.coroutine
def test_remove_entry(hass, manager):
    """Test that we can remove an entry."""
    mock_unload_entry = MagicMock(return_value=mock_coro(True))

    loader.set_component(
        hass, 'test',
        MockModule('comp', async_unload_entry=mock_unload_entry))

    MockConfigEntry(domain='test', entry_id='test1').add_to_manager(manager)
    MockConfigEntry(domain='test', entry_id='test2').add_to_manager(manager)
    MockConfigEntry(domain='test', entry_id='test3').add_to_manager(manager)

    assert [item.entry_id for item in manager.async_entries()] == \
        ['test1', 'test2', 'test3']

    result = yield from manager.async_remove('test2')

    assert result == {
        'require_restart': False
    }
    assert [item.entry_id for item in manager.async_entries()] == \
        ['test1', 'test3']

    assert len(mock_unload_entry.mock_calls) == 1


@asyncio.coroutine
def test_remove_entry_raises(hass, manager):
    """Test if a component raises while removing entry."""
    @asyncio.coroutine
    def mock_unload_entry(hass, entry):
        """Mock unload entry function."""
        raise Exception("BROKEN")

    loader.set_component(
        hass, 'test',
        MockModule('comp', async_unload_entry=mock_unload_entry))

    MockConfigEntry(domain='test', entry_id='test1').add_to_manager(manager)
    MockConfigEntry(domain='test', entry_id='test2').add_to_manager(manager)
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
def test_add_entry_calls_setup_entry(hass, manager):
    """Test we call setup_config_entry."""
    mock_setup_entry = MagicMock(return_value=mock_coro(True))

    loader.set_component(
        hass, 'comp',
        MockModule('comp', async_setup_entry=mock_setup_entry))

    class TestFlow(data_entry_flow.FlowHandler):

        VERSION = 1

        @asyncio.coroutine
        def async_step_init(self, user_input=None):
            return self.async_create_entry(
                title='title',
                data={
                    'token': 'supersecret'
                })

    with patch.dict(config_entries.HANDLERS, {'comp': TestFlow, 'beer': 5}):
        yield from manager.flow.async_init('comp')
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


@asyncio.coroutine
def test_saving_and_loading(hass):
    """Test that we're saving and loading correctly."""
    loader.set_component(hass, 'test', MockModule('test'))

    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5

        @asyncio.coroutine
        def async_step_init(self, user_input=None):
            return self.async_create_entry(
                title='Test Title',
                data={
                    'token': 'abcd'
                }
            )

    with patch.dict(config_entries.HANDLERS, {'test': TestFlow}):
        yield from hass.config_entries.flow.async_init('test')

    class Test2Flow(data_entry_flow.FlowHandler):
        VERSION = 3

        @asyncio.coroutine
        def async_step_init(self, user_input=None):
            return self.async_create_entry(
                title='Test 2 Title',
                data={
                    'username': 'bla'
                }
            )

    json_path = 'homeassistant.util.json.open'

    with patch('homeassistant.config_entries.HANDLERS.get',
               return_value=Test2Flow), \
            patch.object(config_entries, 'SAVE_DELAY', 0):
        yield from hass.config_entries.flow.async_init('test')

    with patch(json_path, mock_open(), create=True) as mock_write:
        # To trigger the call_later
        yield from asyncio.sleep(0, loop=hass.loop)
        # To execute the save
        yield from hass.async_block_till_done()

    # Mock open calls are: open file, context enter, write, context leave
    written = mock_write.mock_calls[2][1][0]

    # Now load written data in new config manager
    manager = config_entries.ConfigEntries(hass, {})

    with patch('os.path.isfile', return_value=True), \
            patch(json_path, mock_open(read_data=written), create=True):
        yield from manager.async_load()

    # Ensure same order
    for orig, loaded in zip(hass.config_entries.async_entries(),
                            manager.async_entries()):
        assert orig.version == loaded.version
        assert orig.domain == loaded.domain
        assert orig.title == loaded.title
        assert orig.data == loaded.data
        assert orig.source == loaded.source


async def test_forward_entry_sets_up_component(hass):
    """Test we setup the component entry is forwarded to."""
    entry = MockConfigEntry(domain='original')

    mock_original_setup_entry = MagicMock(return_value=mock_coro(True))
    loader.set_component(
        hass, 'original',
        MockModule('original', async_setup_entry=mock_original_setup_entry))

    mock_forwarded_setup_entry = MagicMock(return_value=mock_coro(True))
    loader.set_component(
        hass, 'forwarded',
        MockModule('forwarded', async_setup_entry=mock_forwarded_setup_entry))

    await hass.config_entries.async_forward_entry_setup(entry, 'forwarded')
    assert len(mock_original_setup_entry.mock_calls) == 0
    assert len(mock_forwarded_setup_entry.mock_calls) == 1


async def test_forward_entry_does_not_setup_entry_if_setup_fails(hass):
    """Test we do not setup entry if component setup fails."""
    entry = MockConfigEntry(domain='original')

    mock_setup = MagicMock(return_value=mock_coro(False))
    mock_setup_entry = MagicMock()
    hass, loader.set_component(hass, 'forwarded', MockModule(
        'forwarded',
        async_setup=mock_setup,
        async_setup_entry=mock_setup_entry,
    ))

    await hass.config_entries.async_forward_entry_setup(entry, 'forwarded')
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0


async def test_discovery_notification(hass):
    """Test that we create/dismiss a notification when source is discovery."""
    loader.set_component(hass, 'test', MockModule('test'))
    await async_setup_component(hass, 'persistent_notification', {})

    class TestFlow(data_entry_flow.FlowHandler):
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
            'test', source=data_entry_flow.SOURCE_DISCOVERY)

    await hass.async_block_till_done()
    state = hass.states.get('persistent_notification.config_entry_discovery')
    assert state is not None

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()
    state = hass.states.get('persistent_notification.config_entry_discovery')
    assert state is None
