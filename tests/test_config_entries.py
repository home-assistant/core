"""Test the config manager."""
import asyncio
from unittest.mock import MagicMock, patch, mock_open

import pytest
import voluptuous as vol

from homeassistant import config_entries, loader
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
        'comp',
        MockModule('comp', async_setup_entry=mock_setup_entry))

    result = yield from async_setup_component(hass, 'comp', {})
    assert result
    assert len(mock_setup_entry.mock_calls) == 1


@asyncio.coroutine
def test_remove_entry(manager):
    """Test that we can remove an entry."""
    mock_unload_entry = MagicMock(return_value=mock_coro(True))

    loader.set_component(
        'test',
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
def test_remove_entry_raises(manager):
    """Test if a component raises while removing entry."""
    @asyncio.coroutine
    def mock_unload_entry(hass, entry):
        """Mock unload entry function."""
        raise Exception("BROKEN")

    loader.set_component(
        'test',
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
        'comp',
        MockModule('comp', async_setup_entry=mock_setup_entry))

    class TestFlow(config_entries.ConfigFlowHandler):

        VERSION = 1

        @asyncio.coroutine
        def async_step_init(self, user_input=None):
            return self.async_create_entry(
                title='title',
                data={
                    'token': 'supersecret'
                })

    with patch.dict(config_entries.HANDLERS, {'comp': TestFlow}):
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
    class TestFlow(config_entries.ConfigFlowHandler):
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

    class Test2Flow(config_entries.ConfigFlowHandler):
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


#######################
#  FLOW MANAGER TESTS #
#######################

@asyncio.coroutine
def test_configure_reuses_handler_instance(manager):
    """Test that we reuse instances."""
    class TestFlow(config_entries.ConfigFlowHandler):
        handle_count = 0

        @asyncio.coroutine
        def async_step_init(self, user_input=None):
            self.handle_count += 1
            return self.async_show_form(
                errors={'base': str(self.handle_count)},
                step_id='init')

    with patch.dict(config_entries.HANDLERS, {'test': TestFlow}):
        form = yield from manager.flow.async_init('test')
        assert form['errors']['base'] == '1'
        form = yield from manager.flow.async_configure(form['flow_id'])
        assert form['errors']['base'] == '2'
        assert len(manager.flow.async_progress()) == 1
        assert len(manager.async_entries()) == 0


@asyncio.coroutine
def test_configure_two_steps(manager):
    """Test that we reuse instances."""
    class TestFlow(config_entries.ConfigFlowHandler):
        VERSION = 1

        @asyncio.coroutine
        def async_step_init(self, user_input=None):
            if user_input is not None:
                self.init_data = user_input
                return self.async_step_second()
            return self.async_show_form(
                step_id='init',
                data_schema=vol.Schema([str])
            )

        @asyncio.coroutine
        def async_step_second(self, user_input=None):
            if user_input is not None:
                return self.async_create_entry(
                    title='Test Entry',
                    data=self.init_data + user_input
                )
            return self.async_show_form(
                step_id='second',
                data_schema=vol.Schema([str])
            )

    with patch.dict(config_entries.HANDLERS, {'test': TestFlow}):
        form = yield from manager.flow.async_init('test')

        with pytest.raises(vol.Invalid):
            form = yield from manager.flow.async_configure(
                form['flow_id'], 'INCORRECT-DATA')

        form = yield from manager.flow.async_configure(
            form['flow_id'], ['INIT-DATA'])
        form = yield from manager.flow.async_configure(
            form['flow_id'], ['SECOND-DATA'])
        assert form['type'] == config_entries.RESULT_TYPE_CREATE_ENTRY
        assert len(manager.flow.async_progress()) == 0
        assert len(manager.async_entries()) == 1
        entry = manager.async_entries()[0]
        assert entry.domain == 'test'
        assert entry.data == ['INIT-DATA', 'SECOND-DATA']


@asyncio.coroutine
def test_show_form(manager):
    """Test that abort removes the flow from progress."""
    schema = vol.Schema({
        vol.Required('username'): str,
        vol.Required('password'): str
    })

    class TestFlow(config_entries.ConfigFlowHandler):
        @asyncio.coroutine
        def async_step_init(self, user_input=None):
            return self.async_show_form(
                step_id='init',
                data_schema=schema,
                errors={
                    'username': 'Should be unique.'
                }
            )

    with patch.dict(config_entries.HANDLERS, {'test': TestFlow}):
        form = yield from manager.flow.async_init('test')
        assert form['type'] == 'form'
        assert form['data_schema'] is schema
        assert form['errors'] == {
            'username': 'Should be unique.'
        }


@asyncio.coroutine
def test_abort_removes_instance(manager):
    """Test that abort removes the flow from progress."""
    class TestFlow(config_entries.ConfigFlowHandler):
        is_new = True

        @asyncio.coroutine
        def async_step_init(self, user_input=None):
            old = self.is_new
            self.is_new = False
            return self.async_abort(reason=str(old))

    with patch.dict(config_entries.HANDLERS, {'test': TestFlow}):
        form = yield from manager.flow.async_init('test')
        assert form['reason'] == 'True'
        assert len(manager.flow.async_progress()) == 0
        assert len(manager.async_entries()) == 0
        form = yield from manager.flow.async_init('test')
        assert form['reason'] == 'True'
        assert len(manager.flow.async_progress()) == 0
        assert len(manager.async_entries()) == 0


@asyncio.coroutine
def test_create_saves_data(manager):
    """Test creating a config entry."""
    class TestFlow(config_entries.ConfigFlowHandler):
        VERSION = 5

        @asyncio.coroutine
        def async_step_init(self, user_input=None):
            return self.async_create_entry(
                title='Test Title',
                data='Test Data'
            )

    with patch.dict(config_entries.HANDLERS, {'test': TestFlow}):
        yield from manager.flow.async_init('test')
        assert len(manager.flow.async_progress()) == 0
        assert len(manager.async_entries()) == 1

        entry = manager.async_entries()[0]
        assert entry.version == 5
        assert entry.domain == 'test'
        assert entry.title == 'Test Title'
        assert entry.data == 'Test Data'
        assert entry.source == config_entries.SOURCE_USER


@asyncio.coroutine
def test_discovery_init_flow(manager):
    """Test a flow initialized by discovery."""
    class TestFlow(config_entries.ConfigFlowHandler):
        VERSION = 5

        @asyncio.coroutine
        def async_step_discovery(self, info):
            return self.async_create_entry(title=info['id'], data=info)

    data = {
        'id': 'hello',
        'token': 'secret'
    }

    with patch.dict(config_entries.HANDLERS, {'test': TestFlow}):
        yield from manager.flow.async_init(
            'test', source=config_entries.SOURCE_DISCOVERY, data=data)
        assert len(manager.flow.async_progress()) == 0
        assert len(manager.async_entries()) == 1

        entry = manager.async_entries()[0]
        assert entry.version == 5
        assert entry.domain == 'test'
        assert entry.title == 'hello'
        assert entry.data == data
        assert entry.source == config_entries.SOURCE_DISCOVERY
