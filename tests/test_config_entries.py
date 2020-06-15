"""Test the config manager."""
import asyncio
from datetime import timedelta

import pytest

from homeassistant import config_entries, data_entry_flow, loader
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from tests.async_mock import AsyncMock, patch
from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockModule,
    MockPlatform,
    async_fire_time_changed,
    mock_coro,
    mock_entity_platform,
    mock_integration,
    mock_registry,
)


@pytest.fixture(autouse=True)
def mock_handlers():
    """Mock config flows."""

    class MockFlowHandler(config_entries.ConfigFlow):
        """Define a mock flow handler."""

        VERSION = 1

    with patch.dict(
        config_entries.HANDLERS, {"comp": MockFlowHandler, "test": MockFlowHandler}
    ):
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
    entry = MockConfigEntry(domain="comp")
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)
    mock_migrate_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    result = await async_setup_component(hass, "comp", {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_LOADED


async def test_call_async_migrate_entry(hass):
    """Test we call <component>.async_migrate_entry when version mismatch."""
    entry = MockConfigEntry(domain="comp")
    entry.version = 2
    entry.add_to_hass(hass)

    mock_migrate_entry = AsyncMock(return_value=True)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    result = await async_setup_component(hass, "comp", {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_LOADED


async def test_call_async_migrate_entry_failure_false(hass):
    """Test migration fails if returns false."""
    entry = MockConfigEntry(domain="comp")
    entry.version = 2
    entry.add_to_hass(hass)

    mock_migrate_entry = AsyncMock(return_value=False)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    result = await async_setup_component(hass, "comp", {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state == config_entries.ENTRY_STATE_MIGRATION_ERROR


async def test_call_async_migrate_entry_failure_exception(hass):
    """Test migration fails if exception raised."""
    entry = MockConfigEntry(domain="comp")
    entry.version = 2
    entry.add_to_hass(hass)

    mock_migrate_entry = AsyncMock(side_effect=Exception)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    result = await async_setup_component(hass, "comp", {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state == config_entries.ENTRY_STATE_MIGRATION_ERROR


async def test_call_async_migrate_entry_failure_not_bool(hass):
    """Test migration fails if boolean not returned."""
    entry = MockConfigEntry(domain="comp")
    entry.version = 2
    entry.add_to_hass(hass)

    mock_migrate_entry = AsyncMock(return_value=None)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    result = await async_setup_component(hass, "comp", {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state == config_entries.ENTRY_STATE_MIGRATION_ERROR


async def test_call_async_migrate_entry_failure_not_supported(hass):
    """Test migration fails if async_migrate_entry not implemented."""
    entry = MockConfigEntry(domain="comp")
    entry.version = 2
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_entity_platform(hass, "config_flow.comp", None)

    result = await async_setup_component(hass, "comp", {})
    assert result
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state == config_entries.ENTRY_STATE_MIGRATION_ERROR


async def test_remove_entry(hass, manager):
    """Test that we can remove an entry."""

    async def mock_setup_entry(hass, entry):
        """Mock setting up entry."""
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "light")
        )
        return True

    async def mock_unload_entry(hass, entry):
        """Mock unloading an entry."""
        result = await hass.config_entries.async_forward_entry_unload(entry, "light")
        assert result
        return result

    mock_remove_entry = AsyncMock(return_value=None)

    entity = MockEntity(unique_id="1234", name="Test Entity")

    async def mock_setup_entry_platform(hass, entry, async_add_entities):
        """Mock setting up platform."""
        async_add_entities([entity])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
            async_remove_entry=mock_remove_entry,
        ),
    )
    mock_entity_platform(
        hass, "light.test", MockPlatform(async_setup_entry=mock_setup_entry_platform)
    )
    mock_entity_platform(hass, "config_flow.test", None)

    MockConfigEntry(domain="test_other", entry_id="test1").add_to_manager(manager)
    entry = MockConfigEntry(domain="test", entry_id="test2")
    entry.add_to_manager(manager)
    MockConfigEntry(domain="test_other", entry_id="test3").add_to_manager(manager)

    # Check all config entries exist
    assert [item.entry_id for item in manager.async_entries()] == [
        "test1",
        "test2",
        "test3",
    ]

    # Setup entry
    await entry.async_setup(hass)
    await hass.async_block_till_done()

    # Check entity state got added
    assert hass.states.get("light.test_entity") is not None
    assert len(hass.states.async_all()) == 1

    # Check entity got added to entity registry
    ent_reg = await hass.helpers.entity_registry.async_get_registry()
    assert len(ent_reg.entities) == 1
    entity_entry = list(ent_reg.entities.values())[0]
    assert entity_entry.config_entry_id == entry.entry_id

    # Remove entry
    result = await manager.async_remove("test2")
    await hass.async_block_till_done()

    # Check that unload went well and so no need to restart
    assert result == {"require_restart": False}

    # Check the remove callback was invoked.
    assert mock_remove_entry.call_count == 1

    # Check that config entry was removed.
    assert [item.entry_id for item in manager.async_entries()] == ["test1", "test3"]

    # Check that entity state has been removed
    assert hass.states.get("light.test_entity") is None
    assert len(hass.states.async_all()) == 0

    # Check that entity registry entry has been removed
    entity_entry_list = list(ent_reg.entities.values())
    assert not entity_entry_list


async def test_remove_entry_handles_callback_error(hass, manager):
    """Test that exceptions in the remove callback are handled."""
    mock_setup_entry = AsyncMock(return_value=True)
    mock_unload_entry = AsyncMock(return_value=True)
    mock_remove_entry = AsyncMock(return_value=None)
    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
            async_remove_entry=mock_remove_entry,
        ),
    )
    entry = MockConfigEntry(domain="test", entry_id="test1")
    entry.add_to_manager(manager)
    # Check all config entries exist
    assert [item.entry_id for item in manager.async_entries()] == ["test1"]
    # Setup entry
    await entry.async_setup(hass)
    await hass.async_block_till_done()

    # Remove entry
    result = await manager.async_remove("test1")
    await hass.async_block_till_done()
    # Check that unload went well and so no need to restart
    assert result == {"require_restart": False}
    # Check the remove callback was invoked.
    assert mock_remove_entry.call_count == 1
    # Check that config entry was removed.
    assert [item.entry_id for item in manager.async_entries()] == []


async def test_remove_entry_raises(hass, manager):
    """Test if a component raises while removing entry."""

    async def mock_unload_entry(hass, entry):
        """Mock unload entry function."""
        raise Exception("BROKEN")

    mock_integration(hass, MockModule("comp", async_unload_entry=mock_unload_entry))

    MockConfigEntry(domain="test", entry_id="test1").add_to_manager(manager)
    MockConfigEntry(
        domain="comp", entry_id="test2", state=config_entries.ENTRY_STATE_LOADED
    ).add_to_manager(manager)
    MockConfigEntry(domain="test", entry_id="test3").add_to_manager(manager)

    assert [item.entry_id for item in manager.async_entries()] == [
        "test1",
        "test2",
        "test3",
    ]

    result = await manager.async_remove("test2")

    assert result == {"require_restart": True}
    assert [item.entry_id for item in manager.async_entries()] == ["test1", "test3"]


async def test_remove_entry_if_not_loaded(hass, manager):
    """Test that we can remove an entry that is not loaded."""
    mock_unload_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_unload_entry=mock_unload_entry))

    MockConfigEntry(domain="test", entry_id="test1").add_to_manager(manager)
    MockConfigEntry(domain="comp", entry_id="test2").add_to_manager(manager)
    MockConfigEntry(domain="test", entry_id="test3").add_to_manager(manager)

    assert [item.entry_id for item in manager.async_entries()] == [
        "test1",
        "test2",
        "test3",
    ]

    result = await manager.async_remove("test2")

    assert result == {"require_restart": False}
    assert [item.entry_id for item in manager.async_entries()] == ["test1", "test3"]

    assert len(mock_unload_entry.mock_calls) == 0


async def test_remove_entry_if_integration_deleted(hass, manager):
    """Test that we can remove an entry when the integration is deleted."""
    mock_unload_entry = AsyncMock(return_value=True)

    MockConfigEntry(domain="test", entry_id="test1").add_to_manager(manager)
    MockConfigEntry(domain="comp", entry_id="test2").add_to_manager(manager)
    MockConfigEntry(domain="test", entry_id="test3").add_to_manager(manager)

    assert [item.entry_id for item in manager.async_entries()] == [
        "test1",
        "test2",
        "test3",
    ]

    result = await manager.async_remove("test2")

    assert result == {"require_restart": False}
    assert [item.entry_id for item in manager.async_entries()] == ["test1", "test3"]

    assert len(mock_unload_entry.mock_calls) == 0


async def test_add_entry_calls_setup_entry(hass, manager):
    """Test we call setup_config_entry."""
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            return self.async_create_entry(title="title", data={"token": "supersecret"})

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow, "beer": 5}):
        await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry = mock_setup_entry.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry.data == {"token": "supersecret"}


async def test_entries_gets_entries(manager):
    """Test entries are filtered by domain."""
    MockConfigEntry(domain="test").add_to_manager(manager)
    entry1 = MockConfigEntry(domain="test2")
    entry1.add_to_manager(manager)
    entry2 = MockConfigEntry(domain="test2")
    entry2.add_to_manager(manager)

    assert manager.async_entries("test2") == [entry1, entry2]


async def test_domains_gets_uniques(manager):
    """Test we only return each domain once."""
    MockConfigEntry(domain="test").add_to_manager(manager)
    MockConfigEntry(domain="test2").add_to_manager(manager)
    MockConfigEntry(domain="test2").add_to_manager(manager)
    MockConfigEntry(domain="test").add_to_manager(manager)
    MockConfigEntry(domain="test3").add_to_manager(manager)

    assert manager.async_domains() == ["test", "test2", "test3"]


async def test_saving_and_loading(hass):
    """Test that we're saving and loading correctly."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=lambda *args: mock_coro(True))
    )
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 5
        CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("unique")
            return self.async_create_entry(title="Test Title", data={"token": "abcd"})

    with patch.dict(config_entries.HANDLERS, {"test": TestFlow}):
        await hass.config_entries.flow.async_init(
            "test", context={"source": config_entries.SOURCE_USER}
        )

    class Test2Flow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 3
        CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

        async def async_step_user(self, user_input=None):
            """Test user step."""
            return self.async_create_entry(
                title="Test 2 Title", data={"username": "bla"}
            )

    with patch("homeassistant.config_entries.HANDLERS.get", return_value=Test2Flow):
        await hass.config_entries.flow.async_init(
            "test", context={"source": config_entries.SOURCE_USER}
        )

    assert len(hass.config_entries.async_entries()) == 2

    # To trigger the call_later
    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=1))
    # To execute the save
    await hass.async_block_till_done()

    # Now load written data in new config manager
    manager = config_entries.ConfigEntries(hass, {})
    await manager.async_initialize()

    assert len(manager.async_entries()) == 2

    # Ensure same order
    for orig, loaded in zip(
        hass.config_entries.async_entries(), manager.async_entries()
    ):
        assert orig.version == loaded.version
        assert orig.domain == loaded.domain
        assert orig.title == loaded.title
        assert orig.data == loaded.data
        assert orig.source == loaded.source
        assert orig.connection_class == loaded.connection_class
        assert orig.unique_id == loaded.unique_id


async def test_forward_entry_sets_up_component(hass):
    """Test we setup the component entry is forwarded to."""
    entry = MockConfigEntry(domain="original")

    mock_original_setup_entry = AsyncMock(return_value=True)
    mock_integration(
        hass, MockModule("original", async_setup_entry=mock_original_setup_entry)
    )

    mock_forwarded_setup_entry = AsyncMock(return_value=True)
    mock_integration(
        hass, MockModule("forwarded", async_setup_entry=mock_forwarded_setup_entry)
    )

    await hass.config_entries.async_forward_entry_setup(entry, "forwarded")
    assert len(mock_original_setup_entry.mock_calls) == 0
    assert len(mock_forwarded_setup_entry.mock_calls) == 1


async def test_forward_entry_does_not_setup_entry_if_setup_fails(hass):
    """Test we do not set up entry if component setup fails."""
    entry = MockConfigEntry(domain="original")

    mock_setup = AsyncMock(return_value=False)
    mock_setup_entry = AsyncMock()
    mock_integration(
        hass,
        MockModule(
            "forwarded", async_setup=mock_setup, async_setup_entry=mock_setup_entry
        ),
    )

    await hass.config_entries.async_forward_entry_setup(entry, "forwarded")
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0


async def test_discovery_notification(hass):
    """Test that we create/dismiss a notification when source is discovery."""
    mock_integration(hass, MockModule("test"))
    mock_entity_platform(hass, "config_flow.test", None)
    await async_setup_component(hass, "persistent_notification", {})

    with patch.dict(config_entries.HANDLERS):

        class TestFlow(config_entries.ConfigFlow, domain="test"):
            """Test flow."""

            VERSION = 5

            async def async_step_discovery(self, discovery_info):
                """Test discovery step."""
                return self.async_show_form(step_id="discovery_confirm")

            async def async_step_discovery_confirm(self, discovery_info):
                """Test discovery confirm step."""
                return self.async_create_entry(
                    title="Test Title", data={"token": "abcd"}
                )

        result = await hass.config_entries.flow.async_init(
            "test", context={"source": config_entries.SOURCE_DISCOVERY}
        )

        await hass.async_block_till_done()
        state = hass.states.get("persistent_notification.config_entry_discovery")
        assert state is not None

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()
        state = hass.states.get("persistent_notification.config_entry_discovery")
        assert state is None


async def test_discovery_notification_not_created(hass):
    """Test that we not create a notification when discovery is aborted."""
    mock_integration(hass, MockModule("test"))
    mock_entity_platform(hass, "config_flow.test", None)
    await async_setup_component(hass, "persistent_notification", {})

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 5

        async def async_step_discovery(self, discovery_info):
            """Test discovery step."""
            return self.async_abort(reason="test")

    with patch.dict(config_entries.HANDLERS, {"test": TestFlow}):
        await hass.config_entries.flow.async_init(
            "test", context={"source": config_entries.SOURCE_DISCOVERY}
        )

    await hass.async_block_till_done()
    state = hass.states.get("persistent_notification.config_entry_discovery")
    assert state is None


async def test_loading_default_config(hass):
    """Test loading the default config."""
    manager = config_entries.ConfigEntries(hass, {})

    with patch("homeassistant.util.json.open", side_effect=FileNotFoundError):
        await manager.async_initialize()

    assert len(manager.async_entries()) == 0


async def test_updating_entry_data(manager):
    """Test that we can update an entry data."""
    entry = MockConfigEntry(
        domain="test",
        data={"first": True},
        state=config_entries.ENTRY_STATE_SETUP_ERROR,
    )
    entry.add_to_manager(manager)

    manager.async_update_entry(entry)
    assert entry.data == {"first": True}

    manager.async_update_entry(entry, data={"second": True})
    assert entry.data == {"second": True}


async def test_updating_entry_system_options(manager):
    """Test that we can update an entry data."""
    entry = MockConfigEntry(
        domain="test",
        data={"first": True},
        state=config_entries.ENTRY_STATE_SETUP_ERROR,
        system_options={"disable_new_entities": True},
    )
    entry.add_to_manager(manager)

    assert entry.system_options.disable_new_entities

    entry.system_options.update(disable_new_entities=False)
    assert not entry.system_options.disable_new_entities


async def test_update_entry_options_and_trigger_listener(hass, manager):
    """Test that we can update entry options and trigger listener."""
    entry = MockConfigEntry(domain="test", options={"first": True})
    entry.add_to_manager(manager)

    async def update_listener(hass, entry):
        """Test function."""
        assert entry.options == {"second": True}

    entry.add_update_listener(update_listener)

    manager.async_update_entry(entry, options={"second": True})

    assert entry.options == {"second": True}


async def test_setup_raise_not_ready(hass, caplog):
    """Test a setup raising not ready."""
    entry = MockConfigEntry(domain="test")

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryNotReady)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_entity_platform(hass, "config_flow.test", None)

    with patch("homeassistant.helpers.event.async_call_later") as mock_call:
        await entry.async_setup(hass)

    assert len(mock_call.mock_calls) == 1
    assert "Config entry for test not ready yet" in caplog.text
    p_hass, p_wait_time, p_setup = mock_call.mock_calls[0][1]

    assert p_hass is hass
    assert p_wait_time == 5
    assert entry.state == config_entries.ENTRY_STATE_SETUP_RETRY

    mock_setup_entry.side_effect = None
    mock_setup_entry.return_value = True

    await p_setup(None)
    assert entry.state == config_entries.ENTRY_STATE_LOADED


async def test_setup_retrying_during_unload(hass):
    """Test if we unload an entry that is in retry mode."""
    entry = MockConfigEntry(domain="test")

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryNotReady)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_entity_platform(hass, "config_flow.test", None)

    with patch("homeassistant.helpers.event.async_call_later") as mock_call:
        await entry.async_setup(hass)

    assert entry.state == config_entries.ENTRY_STATE_SETUP_RETRY
    assert len(mock_call.return_value.mock_calls) == 0

    await entry.async_unload(hass)

    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
    assert len(mock_call.return_value.mock_calls) == 1


async def test_entry_options(hass, manager):
    """Test that we can set options on an entry."""
    entry = MockConfigEntry(domain="test", data={"first": True}, options=None)
    entry.add_to_manager(manager)

    class TestFlow:
        """Test flow."""

        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            """Test options flow."""

            class OptionsFlowHandler(data_entry_flow.FlowHandler):
                """Test options flow handler."""

            return OptionsFlowHandler()

    config_entries.HANDLERS["test"] = TestFlow()
    flow = await manager.options.async_create_flow(
        entry.entry_id, context={"source": "test"}, data=None
    )

    flow.handler = entry.entry_id  # Used to keep reference to config entry

    await manager.options.async_finish_flow(flow, {"data": {"second": True}})

    assert entry.data == {"first": True}
    assert entry.options == {"second": True}


async def test_entry_setup_succeed(hass, manager):
    """Test that we can setup an entry."""
    entry = MockConfigEntry(domain="comp", state=config_entries.ENTRY_STATE_NOT_LOADED)
    entry.add_to_hass(hass)

    mock_setup = AsyncMock(return_value=True)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule("comp", async_setup=mock_setup, async_setup_entry=mock_setup_entry),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    assert await manager.async_setup(entry.entry_id)
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_LOADED


@pytest.mark.parametrize(
    "state",
    (
        config_entries.ENTRY_STATE_LOADED,
        config_entries.ENTRY_STATE_SETUP_ERROR,
        config_entries.ENTRY_STATE_MIGRATION_ERROR,
        config_entries.ENTRY_STATE_SETUP_RETRY,
        config_entries.ENTRY_STATE_FAILED_UNLOAD,
    ),
)
async def test_entry_setup_invalid_state(hass, manager, state):
    """Test that we cannot setup an entry with invalid state."""
    entry = MockConfigEntry(domain="comp", state=state)
    entry.add_to_hass(hass)

    mock_setup = AsyncMock(return_value=True)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule("comp", async_setup=mock_setup, async_setup_entry=mock_setup_entry),
    )

    with pytest.raises(config_entries.OperationNotAllowed):
        assert await manager.async_setup(entry.entry_id)

    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state == state


async def test_entry_unload_succeed(hass, manager):
    """Test that we can unload an entry."""
    entry = MockConfigEntry(domain="comp", state=config_entries.ENTRY_STATE_LOADED)
    entry.add_to_hass(hass)

    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_unload_entry=async_unload_entry))

    assert await manager.async_unload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED


@pytest.mark.parametrize(
    "state",
    (
        config_entries.ENTRY_STATE_NOT_LOADED,
        config_entries.ENTRY_STATE_SETUP_ERROR,
        config_entries.ENTRY_STATE_SETUP_RETRY,
    ),
)
async def test_entry_unload_failed_to_load(hass, manager, state):
    """Test that we can unload an entry."""
    entry = MockConfigEntry(domain="comp", state=state)
    entry.add_to_hass(hass)

    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_unload_entry=async_unload_entry))

    assert await manager.async_unload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 0
    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED


@pytest.mark.parametrize(
    "state",
    (
        config_entries.ENTRY_STATE_MIGRATION_ERROR,
        config_entries.ENTRY_STATE_FAILED_UNLOAD,
    ),
)
async def test_entry_unload_invalid_state(hass, manager, state):
    """Test that we cannot unload an entry with invalid state."""
    entry = MockConfigEntry(domain="comp", state=state)
    entry.add_to_hass(hass)

    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_unload_entry=async_unload_entry))

    with pytest.raises(config_entries.OperationNotAllowed):
        assert await manager.async_unload(entry.entry_id)

    assert len(async_unload_entry.mock_calls) == 0
    assert entry.state == state


async def test_entry_reload_succeed(hass, manager):
    """Test that we can reload an entry."""
    entry = MockConfigEntry(domain="comp", state=config_entries.ENTRY_STATE_LOADED)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    assert await manager.async_reload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 1
    assert len(async_setup.mock_calls) == 1
    assert len(async_setup_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_LOADED


@pytest.mark.parametrize(
    "state",
    (
        config_entries.ENTRY_STATE_NOT_LOADED,
        config_entries.ENTRY_STATE_SETUP_ERROR,
        config_entries.ENTRY_STATE_SETUP_RETRY,
    ),
)
async def test_entry_reload_not_loaded(hass, manager, state):
    """Test that we can reload an entry."""
    entry = MockConfigEntry(domain="comp", state=state)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    assert await manager.async_reload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 0
    assert len(async_setup.mock_calls) == 1
    assert len(async_setup_entry.mock_calls) == 1
    assert entry.state == config_entries.ENTRY_STATE_LOADED


@pytest.mark.parametrize(
    "state",
    (
        config_entries.ENTRY_STATE_MIGRATION_ERROR,
        config_entries.ENTRY_STATE_FAILED_UNLOAD,
    ),
)
async def test_entry_reload_error(hass, manager, state):
    """Test that we can reload an entry."""
    entry = MockConfigEntry(domain="comp", state=state)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )

    with pytest.raises(config_entries.OperationNotAllowed):
        assert await manager.async_reload(entry.entry_id)

    assert len(async_unload_entry.mock_calls) == 0
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 0

    assert entry.state == state


async def test_init_custom_integration(hass):
    """Test initializing flow for custom integration."""
    integration = loader.Integration(
        hass,
        "custom_components.hue",
        None,
        {"name": "Hue", "dependencies": [], "requirements": [], "domain": "hue"},
    )
    with pytest.raises(data_entry_flow.UnknownHandler):
        with patch(
            "homeassistant.loader.async_get_integration", return_value=integration,
        ):
            await hass.config_entries.flow.async_init("bla")


async def test_support_entry_unload(hass):
    """Test unloading entry."""
    assert await config_entries.support_entry_unload(hass, "light")
    assert not await config_entries.support_entry_unload(hass, "auth")


async def test_reload_entry_entity_registry_ignores_no_entry(hass):
    """Test reloading entry in entity registry skips if no config entry linked."""
    handler = config_entries.EntityRegistryDisabledHandler(hass)
    registry = mock_registry(hass)

    # Test we ignore entities without config entry
    entry = registry.async_get_or_create("light", "hue", "123")
    registry.async_update_entity(entry.entity_id, disabled_by="user")
    await hass.async_block_till_done()
    assert not handler.changed
    assert handler._remove_call_later is None


async def test_reload_entry_entity_registry_works(hass):
    """Test we schedule an entry to be reloaded if disabled_by is updated."""
    handler = config_entries.EntityRegistryDisabledHandler(hass)
    handler.async_setup()
    registry = mock_registry(hass)

    config_entry = MockConfigEntry(
        domain="comp", state=config_entries.ENTRY_STATE_LOADED
    )
    config_entry.add_to_hass(hass)
    mock_setup_entry = AsyncMock(return_value=True)
    mock_unload_entry = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    # Only changing disabled_by should update trigger
    entity_entry = registry.async_get_or_create(
        "light", "hue", "123", config_entry=config_entry
    )
    registry.async_update_entity(entity_entry.entity_id, name="yo")
    await hass.async_block_till_done()
    assert not handler.changed
    assert handler._remove_call_later is None

    # Disable entity, we should not do anything, only act when enabled.
    registry.async_update_entity(entity_entry.entity_id, disabled_by="user")
    await hass.async_block_till_done()
    assert not handler.changed
    assert handler._remove_call_later is None

    # Enable entity, check we are reloading config entry.
    registry.async_update_entity(entity_entry.entity_id, disabled_by=None)
    await hass.async_block_till_done()
    assert handler.changed == {config_entry.entry_id}
    assert handler._remove_call_later is not None

    async_fire_time_changed(
        hass,
        dt.utcnow()
        + timedelta(
            seconds=config_entries.EntityRegistryDisabledHandler.RELOAD_AFTER_UPDATE_DELAY
            + 1
        ),
    )
    await hass.async_block_till_done()

    assert len(mock_unload_entry.mock_calls) == 1


async def test_unqiue_id_persisted(hass, manager):
    """Test that a unique ID is stored in the config entry."""
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            return self.async_create_entry(title="mock-title", data={})

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )

    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry = mock_setup_entry.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry.unique_id == "mock-unique-id"


async def test_unique_id_existing_entry(hass, manager):
    """Test that we remove an entry if there already is an entry with unique ID."""
    hass.config.components.add("comp")
    MockConfigEntry(
        domain="comp",
        state=config_entries.ENTRY_STATE_LOADED,
        unique_id="mock-unique-id",
    ).add_to_hass(hass)

    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)
    async_remove_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
            async_remove_entry=async_remove_entry,
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            existing_entry = await self.async_set_unique_id("mock-unique-id")

            assert existing_entry is not None

            return self.async_create_entry(title="mock-title", data={"via": "flow"})

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    entries = hass.config_entries.async_entries("comp")
    assert len(entries) == 1
    assert entries[0].data == {"via": "flow"}

    assert len(async_setup_entry.mock_calls) == 1
    assert len(async_unload_entry.mock_calls) == 1
    assert len(async_remove_entry.mock_calls) == 1


async def test_unique_id_update_existing_entry(hass, manager):
    """Test that we update an entry if there already is an entry with unique ID."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        data={"additional": "data", "host": "0.0.0.0"},
        unique_id="mock-unique-id",
    )
    entry.add_to_hass(hass)

    mock_integration(
        hass, MockModule("comp"),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            await self._abort_if_unique_id_configured(updates={"host": "1.1.1.1"})

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == "1.1.1.1"
    assert entry.data["additional"] == "data"


async def test_unique_id_not_update_existing_entry(hass, manager):
    """Test that we do not update an entry if existing entry has the data."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        data={"additional": "data", "host": "0.0.0.0"},
        unique_id="mock-unique-id",
    )
    entry.add_to_hass(hass)

    mock_integration(
        hass, MockModule("comp"),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            await self._abort_if_unique_id_configured(updates={"host": "0.0.0.0"})

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}), patch(
        "homeassistant.config_entries.ConfigEntries.async_update_entry"
    ) as async_update_entry:
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == "0.0.0.0"
    assert entry.data["additional"] == "data"
    assert len(async_update_entry.mock_calls) == 0


async def test_unique_id_in_progress(hass, manager):
    """Test that we abort if there is already a flow in progress with same unique id."""
    mock_integration(hass, MockModule("comp"))
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            return self.async_show_form(step_id="discovery")

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        # Create one to be in progress
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        # Will be canceled
        result2 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "already_in_progress"


async def test_finish_flow_aborts_progress(hass, manager):
    """Test that when finishing a flow, we abort other flows in progress with unique ID."""
    mock_integration(
        hass, MockModule("comp", async_setup_entry=AsyncMock(return_value=True)),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id", raise_on_progress=False)

            if user_input is None:
                return self.async_show_form(step_id="discovery")

            return self.async_create_entry(title="yo", data={})

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        # Create one to be in progress
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        # Will finish and cancel other one.
        result2 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}, data={}
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_unique_id_ignore(hass, manager):
    """Test that we can ignore flows that are in progress and have a unique ID."""
    async_setup_entry = AsyncMock(return_value=False)
    mock_integration(hass, MockModule("comp", async_setup_entry=async_setup_entry))
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user flow."""
            await self.async_set_unique_id("mock-unique-id")
            return self.async_show_form(step_id="discovery")

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        # Create one to be in progress
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result2 = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_IGNORE},
            data={"unique_id": "mock-unique-id"},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    # assert len(hass.config_entries.flow.async_progress()) == 0

    # We should never set up an ignored entry.
    assert len(async_setup_entry.mock_calls) == 0

    entry = hass.config_entries.async_entries("comp")[0]

    assert entry.source == "ignore"
    assert entry.unique_id == "mock-unique-id"


async def test_unignore_step_form(hass, manager):
    """Test that we can ignore flows that are in progress and have a unique ID, then rediscover them."""
    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("comp", async_setup_entry=async_setup_entry))
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_unignore(self, user_input):
            """Test unignore step."""
            unique_id = user_input["unique_id"]
            await self.async_set_unique_id(unique_id)
            return self.async_show_form(step_id="discovery")

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_IGNORE},
            data={"unique_id": "mock-unique-id"},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        entry = hass.config_entries.async_entries("comp")[0]
        assert entry.source == "ignore"
        assert entry.unique_id == "mock-unique-id"
        assert entry.domain == "comp"

        await manager.async_remove(entry.entry_id)

        # Right after removal there shouldn't be an entry or active flows
        assert len(hass.config_entries.async_entries("comp")) == 0
        assert len(hass.config_entries.flow.async_progress()) == 0

        # But after a 'tick' the unignore step has run and we can see an active flow again.
        await hass.async_block_till_done()
        assert len(hass.config_entries.flow.async_progress()) == 1

        # and still not config entries
        assert len(hass.config_entries.async_entries("comp")) == 0


async def test_unignore_create_entry(hass, manager):
    """Test that we can ignore flows that are in progress and have a unique ID, then rediscover them."""
    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("comp", async_setup_entry=async_setup_entry))
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_unignore(self, user_input):
            """Test unignore step."""
            unique_id = user_input["unique_id"]
            await self.async_set_unique_id(unique_id)
            return self.async_create_entry(title="yo", data={})

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_IGNORE},
            data={"unique_id": "mock-unique-id"},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        entry = hass.config_entries.async_entries("comp")[0]
        assert entry.source == "ignore"
        assert entry.unique_id == "mock-unique-id"
        assert entry.domain == "comp"

        await manager.async_remove(entry.entry_id)

        # Right after removal there shouldn't be an entry or flow
        assert len(hass.config_entries.flow.async_progress()) == 0
        assert len(hass.config_entries.async_entries("comp")) == 0

        # But after a 'tick' the unignore step has run and we can see a config entry.
        await hass.async_block_till_done()
        entry = hass.config_entries.async_entries("comp")[0]
        assert entry.source == "unignore"
        assert entry.unique_id == "mock-unique-id"
        assert entry.title == "yo"

        # And still no active flow
        assert len(hass.config_entries.flow.async_progress()) == 0


async def test_unignore_default_impl(hass, manager):
    """Test that resdicovery is a no-op by default."""
    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("comp", async_setup_entry=async_setup_entry))
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_IGNORE},
            data={"unique_id": "mock-unique-id"},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        entry = hass.config_entries.async_entries("comp")[0]
        assert entry.source == "ignore"
        assert entry.unique_id == "mock-unique-id"
        assert entry.domain == "comp"

        await manager.async_remove(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.config_entries.async_entries("comp")) == 0
        assert len(hass.config_entries.flow.async_progress()) == 0


async def test_partial_flows_hidden(hass, manager):
    """Test that flows that don't have a cur_step and haven't finished initing are hidden."""
    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("comp", async_setup_entry=async_setup_entry))
    mock_entity_platform(hass, "config_flow.comp", None)
    await async_setup_component(hass, "persistent_notification", {})

    # A flag to test our assertion that `async_step_discovery` was called and is in its blocked state
    # This simulates if the step was e.g. doing network i/o
    discovery_started = asyncio.Event()

    # A flag to allow `async_step_discovery` to resume after we have verified the uninited flow is not
    # visible and has not triggered a discovery alert. This lets us control when the mocked network
    # i/o is complete.
    pause_discovery = asyncio.Event()

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_discovery(self, discovery_info):
            """Test discovery step."""
            discovery_started.set()
            await pause_discovery.wait()
            return self.async_show_form(step_id="someform")

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        # Start a config entry flow and wait for it to be blocked
        init_task = asyncio.ensure_future(
            manager.flow.async_init(
                "comp",
                context={"source": config_entries.SOURCE_DISCOVERY},
                data={"unique_id": "mock-unique-id"},
            )
        )
        await discovery_started.wait()

        # While it's blocked it shouldn't be visible or trigger discovery notifications
        assert len(hass.config_entries.flow.async_progress()) == 0

        await hass.async_block_till_done()
        state = hass.states.get("persistent_notification.config_entry_discovery")
        assert state is None

        # Let the flow init complete
        pause_discovery.set()

        # When it's complete it should now be visible in async_progress and have triggered
        # discovery notifications
        result = await init_task
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert len(hass.config_entries.flow.async_progress()) == 1

        await hass.async_block_till_done()
        state = hass.states.get("persistent_notification.config_entry_discovery")
        assert state is not None


async def test_async_setup_init_entry(hass):
    """Test a config entry being initialized during integration setup."""

    async def mock_async_setup(hass, config):
        """Mock setup."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                "comp", context={"source": config_entries.SOURCE_IMPORT}, data={},
            )
        )
        return True

    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule(
            "comp", async_setup=mock_async_setup, async_setup_entry=async_setup_entry
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)
    await async_setup_component(hass, "persistent_notification", {})

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_import(self, user_input):
            """Test import step creating entry."""
            return self.async_create_entry(title="title", data={})

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        assert await async_setup_component(hass, "comp", {})

        await hass.async_block_till_done()

        assert len(async_setup_entry.mock_calls) == 1

        entries = hass.config_entries.async_entries("comp")
        assert len(entries) == 1
        assert entries[0].state == config_entries.ENTRY_STATE_LOADED


async def test_async_setup_update_entry(hass):
    """Test a config entry being updated during integration setup."""
    entry = MockConfigEntry(domain="comp", data={"value": "initial"})
    entry.add_to_hass(hass)

    async def mock_async_setup(hass, config):
        """Mock setup."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                "comp", context={"source": config_entries.SOURCE_IMPORT}, data={},
            )
        )
        return True

    async def mock_async_setup_entry(hass, entry):
        """Mock setting up an entry."""
        assert entry.data["value"] == "updated"
        return True

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=mock_async_setup,
            async_setup_entry=mock_async_setup_entry,
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)
    await async_setup_component(hass, "persistent_notification", {})

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_import(self, user_input):
            """Test import step updating existing entry."""
            self.hass.config_entries.async_update_entry(
                entry, data={"value": "updated"}
            )
            return self.async_abort(reason="yo")

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        assert await async_setup_component(hass, "comp", {})

        entries = hass.config_entries.async_entries("comp")
        assert len(entries) == 1
        assert entries[0].state == config_entries.ENTRY_STATE_LOADED
        assert entries[0].data == {"value": "updated"}


@pytest.mark.parametrize(
    "discovery_source",
    (
        config_entries.SOURCE_DISCOVERY,
        config_entries.SOURCE_SSDP,
        config_entries.SOURCE_HOMEKIT,
        config_entries.SOURCE_ZEROCONF,
        config_entries.SOURCE_HASSIO,
    ),
)
async def test_flow_with_default_discovery(hass, manager, discovery_source):
    """Test that finishing a default discovery flow removes the unique ID in the entry."""
    mock_integration(
        hass, MockModule("comp", async_setup_entry=AsyncMock(return_value=True)),
    )
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            if user_input is None:
                return self.async_show_form(step_id="user")

            return self.async_create_entry(title="yo", data={})

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        # Create one to be in progress
        result = await manager.flow.async_init(
            "comp", context={"source": discovery_source}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 1
        assert (
            flows[0]["context"]["unique_id"]
            == config_entries.DEFAULT_DISCOVERY_UNIQUE_ID
        )

        # Finish flow
        result2 = await manager.flow.async_configure(
            result["flow_id"], user_input={"fake": "data"}
        )
        assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    assert len(hass.config_entries.flow.async_progress()) == 0

    entry = hass.config_entries.async_entries("comp")[0]
    assert entry.title == "yo"
    assert entry.source == discovery_source
    assert entry.unique_id is None


async def test_flow_with_default_discovery_with_unique_id(hass, manager):
    """Test discovery flow using the default discovery is ignored when unique ID is set."""
    mock_integration(hass, MockModule("comp"))
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_discovery(self, discovery_info):
            """Test discovery step."""
            await self.async_set_unique_id("mock-unique-id")
            # This call should make no difference, as a unique ID is set
            await self._async_handle_discovery_without_unique_id()
            return self.async_show_form(step_id="mock")

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_DISCOVERY}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["unique_id"] == "mock-unique-id"


async def test_default_discovery_abort_existing_entries(hass, manager):
    """Test that a flow without discovery implementation aborts when a config entry exists."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(domain="comp", data={}, unique_id="mock-unique-id")
    entry.add_to_hass(hass)

    mock_integration(hass, MockModule("comp"))
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_DISCOVERY}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_default_discovery_in_progress(hass, manager):
    """Test that a flow using default discovery can only be triggered once."""
    mock_integration(hass, MockModule("comp"))
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_discovery(self, discovery_info):
            """Test discovery step."""
            await self.async_set_unique_id(discovery_info.get("unique_id"))
            await self._async_handle_discovery_without_unique_id()
            return self.async_show_form(step_id="mock")

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_DISCOVERY},
            data={"unique_id": "mock-unique-id"},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        # Second discovery without a unique ID
        result2 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_DISCOVERY}, data={}
        )
        assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["unique_id"] == "mock-unique-id"


async def test_default_discovery_abort_on_new_unique_flow(hass, manager):
    """Test that a flow using default discovery is aborted when a second flow with unique ID is created."""
    mock_integration(hass, MockModule("comp"))
    mock_entity_platform(hass, "config_flow.comp", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_discovery(self, discovery_info):
            """Test discovery step."""
            await self.async_set_unique_id(discovery_info.get("unique_id"))
            await self._async_handle_discovery_without_unique_id()
            return self.async_show_form(step_id="mock")

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        # First discovery with default, no unique ID
        result2 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_DISCOVERY}, data={}
        )
        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM

        # Second discovery brings in a unique ID
        result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_DISCOVERY},
            data={"unique_id": "mock-unique-id"},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    # Ensure the first one is cancelled and we end up with just the last one
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["unique_id"] == "mock-unique-id"
