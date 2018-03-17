"""Test the entity helper."""
# pylint: disable=protected-access
import asyncio
from unittest.mock import MagicMock, patch

import pytest

import homeassistant.helpers.entity as entity
from homeassistant.const import ATTR_HIDDEN, ATTR_DEVICE_CLASS
from homeassistant.config import DATA_CUSTOMIZE
from homeassistant.helpers.entity_values import EntityValues

from tests.common import get_test_home_assistant


def test_generate_entity_id_requires_hass_or_ids():
    """Ensure we require at least hass or current ids."""
    fmt = 'test.{}'
    with pytest.raises(ValueError):
        entity.generate_entity_id(fmt, 'hello world')


def test_generate_entity_id_given_keys():
    """Test generating an entity id given current ids."""
    fmt = 'test.{}'
    assert entity.generate_entity_id(
        fmt, 'overwrite hidden true', current_ids=[
            'test.overwrite_hidden_true']) == 'test.overwrite_hidden_true_2'
    assert entity.generate_entity_id(
        fmt, 'overwrite hidden true', current_ids=[
            'test.another_entity']) == 'test.overwrite_hidden_true'


def test_generate_entity_id_with_nonlatin_name():
    """Test generate_entity_id given a name containing non-latin characters."""
    fmt = 'test.{}'
    assert entity.generate_entity_id(
        fmt, 'ホームアシスタント', current_ids=[]
    ) == 'test.unnamed_device'


def test_async_update_support(hass):
    """Test async update getting called."""
    sync_update = []
    async_update = []

    class AsyncEntity(entity.Entity):
        entity_id = 'sensor.test'

        def update(self):
            sync_update.append([1])

    ent = AsyncEntity()
    ent.hass = hass

    hass.loop.run_until_complete(ent.async_update_ha_state(True))

    assert len(sync_update) == 1
    assert len(async_update) == 0

    @asyncio.coroutine
    def async_update_func():
        """Async update."""
        async_update.append(1)

    ent.async_update = async_update_func

    hass.loop.run_until_complete(ent.async_update_ha_state(True))

    assert len(sync_update) == 1
    assert len(async_update) == 1


class TestHelpersEntity(object):
    """Test homeassistant.helpers.entity module."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.entity = entity.Entity()
        self.entity.entity_id = 'test.overwrite_hidden_true'
        self.hass = self.entity.hass = get_test_home_assistant()
        self.entity.schedule_update_ha_state()
        self.hass.block_till_done()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_default_hidden_not_in_attributes(self):
        """Test that the default hidden property is set to False."""
        assert ATTR_HIDDEN not in self.hass.states.get(
            self.entity.entity_id).attributes

    def test_overwriting_hidden_property_to_true(self):
        """Test we can overwrite hidden property to True."""
        self.hass.data[DATA_CUSTOMIZE] = EntityValues({
            self.entity.entity_id: {ATTR_HIDDEN: True}})
        self.entity.schedule_update_ha_state()
        self.hass.block_till_done()

        state = self.hass.states.get(self.entity.entity_id)
        assert state.attributes.get(ATTR_HIDDEN)

    def test_generate_entity_id_given_hass(self):
        """Test generating an entity id given hass object."""
        fmt = 'test.{}'
        assert entity.generate_entity_id(
            fmt, 'overwrite hidden true',
            hass=self.hass) == 'test.overwrite_hidden_true_2'

    def test_device_class(self):
        """Test device class attribute."""
        state = self.hass.states.get(self.entity.entity_id)
        assert state.attributes.get(ATTR_DEVICE_CLASS) is None
        with patch('homeassistant.helpers.entity.Entity.device_class',
                   new='test_class'):
            self.entity.schedule_update_ha_state()
            self.hass.block_till_done()
        state = self.hass.states.get(self.entity.entity_id)
        assert state.attributes.get(ATTR_DEVICE_CLASS) == 'test_class'


@asyncio.coroutine
def test_warn_slow_update(hass):
    """Warn we log when entity update takes a long time."""
    update_call = False

    @asyncio.coroutine
    def async_update():
        """Mock async update."""
        nonlocal update_call
        update_call = True

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = 'comp_test.test_entity'
    mock_entity.async_update = async_update

    with patch.object(hass.loop, 'call_later', MagicMock()) \
            as mock_call:
        yield from mock_entity.async_update_ha_state(True)
        assert mock_call.called
        assert len(mock_call.mock_calls) == 2

        timeout, logger_method = mock_call.mock_calls[0][1][:2]

        assert timeout == entity.SLOW_UPDATE_WARNING
        assert logger_method == entity._LOGGER.warning

        assert mock_call().cancel.called

        assert update_call


@asyncio.coroutine
def test_warn_slow_update_with_exception(hass):
    """Warn we log when entity update takes a long time and trow exception."""
    update_call = False

    @asyncio.coroutine
    def async_update():
        """Mock async update."""
        nonlocal update_call
        update_call = True
        raise AssertionError("Fake update error")

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = 'comp_test.test_entity'
    mock_entity.async_update = async_update

    with patch.object(hass.loop, 'call_later', MagicMock()) \
            as mock_call:
        yield from mock_entity.async_update_ha_state(True)
        assert mock_call.called
        assert len(mock_call.mock_calls) == 2

        timeout, logger_method = mock_call.mock_calls[0][1][:2]

        assert timeout == entity.SLOW_UPDATE_WARNING
        assert logger_method == entity._LOGGER.warning

        assert mock_call().cancel.called

        assert update_call


@asyncio.coroutine
def test_warn_slow_device_update_disabled(hass):
    """Disable slow update warning with async_device_update."""
    update_call = False

    @asyncio.coroutine
    def async_update():
        """Mock async update."""
        nonlocal update_call
        update_call = True

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = 'comp_test.test_entity'
    mock_entity.async_update = async_update

    with patch.object(hass.loop, 'call_later', MagicMock()) \
            as mock_call:
        yield from mock_entity.async_device_update(warning=False)

        assert not mock_call.called
        assert update_call


@asyncio.coroutine
def test_async_schedule_update_ha_state(hass):
    """Warn we log when entity update takes a long time and trow exception."""
    update_call = False

    @asyncio.coroutine
    def async_update():
        """Mock async update."""
        nonlocal update_call
        update_call = True

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = 'comp_test.test_entity'
    mock_entity.async_update = async_update

    mock_entity.async_schedule_update_ha_state(True)
    yield from hass.async_block_till_done()

    assert update_call is True


@asyncio.coroutine
def test_async_parallel_updates_with_zero(hass):
    """Test parallel updates with 0 (disabled)."""
    updates = []
    test_lock = asyncio.Event(loop=hass.loop)

    class AsyncEntity(entity.Entity):

        def __init__(self, entity_id, count):
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self._count = count

        @asyncio.coroutine
        def async_update(self):
            """Test update."""
            updates.append(self._count)
            yield from test_lock.wait()

    ent_1 = AsyncEntity("sensor.test_1", 1)
    ent_2 = AsyncEntity("sensor.test_2", 2)

    ent_1.async_schedule_update_ha_state(True)
    ent_2.async_schedule_update_ha_state(True)

    while True:
        if len(updates) == 2:
            break
        yield from asyncio.sleep(0, loop=hass.loop)

    assert len(updates) == 2
    assert updates == [1, 2]

    test_lock.set()


@asyncio.coroutine
def test_async_parallel_updates_with_one(hass):
    """Test parallel updates with 1 (sequential)."""
    updates = []
    test_lock = asyncio.Lock(loop=hass.loop)
    test_semaphore = asyncio.Semaphore(1, loop=hass.loop)

    yield from test_lock.acquire()

    class AsyncEntity(entity.Entity):

        def __init__(self, entity_id, count):
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self._count = count
            self.parallel_updates = test_semaphore

        @asyncio.coroutine
        def async_update(self):
            """Test update."""
            updates.append(self._count)
            yield from test_lock.acquire()

    ent_1 = AsyncEntity("sensor.test_1", 1)
    ent_2 = AsyncEntity("sensor.test_2", 2)
    ent_3 = AsyncEntity("sensor.test_3", 3)

    ent_1.async_schedule_update_ha_state(True)
    ent_2.async_schedule_update_ha_state(True)
    ent_3.async_schedule_update_ha_state(True)

    while True:
        if len(updates) == 1:
            break
        yield from asyncio.sleep(0, loop=hass.loop)

    assert len(updates) == 1
    assert updates == [1]

    test_lock.release()

    while True:
        if len(updates) == 2:
            break
        yield from asyncio.sleep(0, loop=hass.loop)

    assert len(updates) == 2
    assert updates == [1, 2]

    test_lock.release()

    while True:
        if len(updates) == 3:
            break
        yield from asyncio.sleep(0, loop=hass.loop)

    assert len(updates) == 3
    assert updates == [1, 2, 3]

    test_lock.release()


@asyncio.coroutine
def test_async_parallel_updates_with_two(hass):
    """Test parallel updates with 2 (parallel)."""
    updates = []
    test_lock = asyncio.Lock(loop=hass.loop)
    test_semaphore = asyncio.Semaphore(2, loop=hass.loop)

    yield from test_lock.acquire()

    class AsyncEntity(entity.Entity):

        def __init__(self, entity_id, count):
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self._count = count
            self.parallel_updates = test_semaphore

        @asyncio.coroutine
        def async_update(self):
            """Test update."""
            updates.append(self._count)
            yield from test_lock.acquire()

    ent_1 = AsyncEntity("sensor.test_1", 1)
    ent_2 = AsyncEntity("sensor.test_2", 2)
    ent_3 = AsyncEntity("sensor.test_3", 3)
    ent_4 = AsyncEntity("sensor.test_4", 4)

    ent_1.async_schedule_update_ha_state(True)
    ent_2.async_schedule_update_ha_state(True)
    ent_3.async_schedule_update_ha_state(True)
    ent_4.async_schedule_update_ha_state(True)

    while True:
        if len(updates) == 2:
            break
        yield from asyncio.sleep(0, loop=hass.loop)

    assert len(updates) == 2
    assert updates == [1, 2]

    test_lock.release()
    yield from asyncio.sleep(0, loop=hass.loop)
    test_lock.release()

    while True:
        if len(updates) == 4:
            break
        yield from asyncio.sleep(0, loop=hass.loop)

    assert len(updates) == 4
    assert updates == [1, 2, 3, 4]

    test_lock.release()
    yield from asyncio.sleep(0, loop=hass.loop)
    test_lock.release()


@asyncio.coroutine
def test_async_remove_no_platform(hass):
    """Test async_remove method when no platform set."""
    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = 'test.test'
    yield from ent.async_update_ha_state()
    assert len(hass.states.async_entity_ids()) == 1
    yield from ent.async_remove()
    assert len(hass.states.async_entity_ids()) == 0
