"""Test the entity helper."""
# pylint: disable=protected-access,too-many-public-methods
import asyncio
from unittest.mock import MagicMock

import pytest

import homeassistant.helpers.entity as entity
from homeassistant.const import ATTR_HIDDEN

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


def test_async_update_support(event_loop):
    """Test async update getting called."""
    sync_update = []
    async_update = []

    class AsyncEntity(entity.Entity):
        hass = MagicMock()
        entity_id = 'sensor.test'

        def update(self):
            sync_update.append([1])

    ent = AsyncEntity()
    ent.hass.loop = event_loop

    @asyncio.coroutine
    def test():
        yield from ent.async_update_ha_state(True)

    event_loop.run_until_complete(test())

    assert len(sync_update) == 1
    assert len(async_update) == 0

    @asyncio.coroutine
    def async_update_func():
        """Async update."""
        async_update.append(1)

    ent.async_update = async_update_func

    event_loop.run_until_complete(test())

    assert len(sync_update) == 1
    assert len(async_update) == 1


class TestHelpersEntity(object):
    """Test homeassistant.helpers.entity module."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.entity = entity.Entity()
        self.entity.entity_id = 'test.overwrite_hidden_true'
        self.hass = self.entity.hass = get_test_home_assistant()
        self.entity.update_ha_state()

    def teardown_method(self, method):
        """Stop everything that was started."""
        entity.set_customize({})
        self.hass.stop()

    def test_default_hidden_not_in_attributes(self):
        """Test that the default hidden property is set to False."""
        assert ATTR_HIDDEN not in self.hass.states.get(
            self.entity.entity_id).attributes

    def test_overwriting_hidden_property_to_true(self):
        """Test we can overwrite hidden property to True."""
        entity.set_customize({self.entity.entity_id: {ATTR_HIDDEN: True}})
        self.entity.update_ha_state()

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
