"""Test the flow classes."""
import pytest
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.util.decorator import Registry


@pytest.fixture
def manager():
    """Return a flow manager."""
    handlers = Registry()
    entries = []

    async def async_create_flow(handler_name, *, context, data):
        handler = handlers.get(handler_name)

        if handler is None:
            raise data_entry_flow.UnknownHandler

        flow = handler()
        flow.init_step = context.get('init_step', 'init') \
            if context is not None else 'init'
        flow.source = context.get('source') \
            if context is not None else 'user_input'
        return flow

    async def async_add_entry(context, result):
        if (result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY):
            result['source'] = context.get('source') \
                if context is not None else 'user'
            entries.append(result)

    manager = data_entry_flow.FlowManager(
        None, async_create_flow, async_add_entry)
    manager.mock_created_entries = entries
    manager.mock_reg_handler = handlers.register
    return manager


async def test_configure_reuses_handler_instance(manager):
    """Test that we reuse instances."""
    @manager.mock_reg_handler('test')
    class TestFlow(data_entry_flow.FlowHandler):
        handle_count = 0

        async def async_step_init(self, user_input=None):
            self.handle_count += 1
            return self.async_show_form(
                errors={'base': str(self.handle_count)},
                step_id='init')

    form = await manager.async_init('test')
    assert form['errors']['base'] == '1'
    form = await manager.async_configure(form['flow_id'])
    assert form['errors']['base'] == '2'
    assert len(manager.async_progress()) == 1
    assert len(manager.mock_created_entries) == 0


async def test_configure_two_steps(manager):
    """Test that we reuse instances."""
    @manager.mock_reg_handler('test')
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 1

        async def async_step_first(self, user_input=None):
            if user_input is not None:
                self.init_data = user_input
                return await self.async_step_second()
            return self.async_show_form(
                step_id='first',
                data_schema=vol.Schema([str])
            )

        async def async_step_second(self, user_input=None):
            if user_input is not None:
                return self.async_create_entry(
                    title='Test Entry',
                    data=self.init_data + user_input
                )
            return self.async_show_form(
                step_id='second',
                data_schema=vol.Schema([str])
            )

    form = await manager.async_init('test', context={'init_step': 'first'})

    with pytest.raises(vol.Invalid):
        form = await manager.async_configure(
            form['flow_id'], 'INCORRECT-DATA')

    form = await manager.async_configure(
        form['flow_id'], ['INIT-DATA'])
    form = await manager.async_configure(
        form['flow_id'], ['SECOND-DATA'])
    assert form['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 1
    result = manager.mock_created_entries[0]
    assert result['handler'] == 'test'
    assert result['data'] == ['INIT-DATA', 'SECOND-DATA']


async def test_show_form(manager):
    """Test that abort removes the flow from progress."""
    schema = vol.Schema({
        vol.Required('username'): str,
        vol.Required('password'): str
    })

    @manager.mock_reg_handler('test')
    class TestFlow(data_entry_flow.FlowHandler):
        async def async_step_init(self, user_input=None):
            return self.async_show_form(
                step_id='init',
                data_schema=schema,
                errors={
                    'username': 'Should be unique.'
                }
            )

    form = await manager.async_init('test')
    assert form['type'] == 'form'
    assert form['data_schema'] is schema
    assert form['errors'] == {
        'username': 'Should be unique.'
    }


async def test_abort_removes_instance(manager):
    """Test that abort removes the flow from progress."""
    @manager.mock_reg_handler('test')
    class TestFlow(data_entry_flow.FlowHandler):
        is_new = True

        async def async_step_init(self, user_input=None):
            old = self.is_new
            self.is_new = False
            return self.async_abort(reason=str(old))

    form = await manager.async_init('test')
    assert form['reason'] == 'True'
    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 0
    form = await manager.async_init('test')
    assert form['reason'] == 'True'
    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 0


async def test_create_saves_data(manager):
    """Test creating a config entry."""
    @manager.mock_reg_handler('test')
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5

        async def async_step_init(self, user_input=None):
            return self.async_create_entry(
                title='Test Title',
                data='Test Data'
            )

    await manager.async_init('test')
    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 1

    entry = manager.mock_created_entries[0]
    assert entry['version'] == 5
    assert entry['handler'] == 'test'
    assert entry['title'] == 'Test Title'
    assert entry['data'] == 'Test Data'
    assert entry['source'] == 'user'


async def test_discovery_init_flow(manager):
    """Test a flow initialized by discovery."""
    @manager.mock_reg_handler('test')
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5

        async def async_step_init(self, info):
            return self.async_create_entry(title=info['id'], data=info)

    data = {
        'id': 'hello',
        'token': 'secret'
    }

    await manager.async_init(
        'test', context={'source': 'discovery'}, data=data)
    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 1

    entry = manager.mock_created_entries[0]
    assert entry['version'] == 5
    assert entry['handler'] == 'test'
    assert entry['title'] == 'hello'
    assert entry['data'] == data
    assert entry['source'] == 'discovery'
