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

    def test_update_calls_async_update_if_available(self):
        """Test async update getting called."""
        async_update = []

        class AsyncEntity(entity.Entity):
            hass = self.hass
            entity_id = 'sensor.test'

            @asyncio.coroutine
            def async_update(self):
                async_update.append([1])

        ent = AsyncEntity()
        ent.update()
        assert len(async_update) == 1

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
