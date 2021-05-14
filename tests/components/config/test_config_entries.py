"""Test config entries API."""

from collections import OrderedDict
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries as core_ce, data_entry_flow
from homeassistant.components.config import config_entries
from homeassistant.config_entries import HANDLERS
from homeassistant.core import callback
from homeassistant.generated import config_flows
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_entity_platform,
    mock_integration,
)


@pytest.fixture(autouse=True)
def mock_test_component(hass):
    """Ensure a component called 'test' exists."""
    mock_integration(hass, MockModule("test"))


@pytest.fixture
def client(hass, hass_client):
    """Fixture that can interact with the config manager API."""
    hass.loop.run_until_complete(async_setup_component(hass, "http", {}))
    hass.loop.run_until_complete(config_entries.async_setup(hass))
    yield hass.loop.run_until_complete(hass_client())


async def test_get_entries(hass, client):
    """Test get entries."""
    with patch.dict(HANDLERS, clear=True):

        @HANDLERS.register("comp1")
        class Comp1ConfigFlow:
            """Config flow with options flow."""

            @staticmethod
            @callback
            def async_get_options_flow(config, options):
                """Get options flow."""
                pass

        hass.helpers.config_entry_flow.register_discovery_flow(
            "comp2", "Comp 2", lambda: None
        )

        entry = MockConfigEntry(
            domain="comp1",
            title="Test 1",
            source="bla",
        )
        entry.supports_unload = True
        entry.add_to_hass(hass)
        MockConfigEntry(
            domain="comp2",
            title="Test 2",
            source="bla2",
            state=core_ce.ENTRY_STATE_SETUP_ERROR,
            reason="Unsupported API",
        ).add_to_hass(hass)
        MockConfigEntry(
            domain="comp3",
            title="Test 3",
            source="bla3",
            disabled_by=core_ce.DISABLED_USER,
        ).add_to_hass(hass)

        resp = await client.get("/api/config/config_entries/entry")
        assert resp.status == 200
        data = await resp.json()
        for entry in data:
            entry.pop("entry_id")
        assert data == [
            {
                "domain": "comp1",
                "title": "Test 1",
                "source": "bla",
                "state": "not_loaded",
                "supports_options": True,
                "supports_unload": True,
                "disabled_by": None,
                "reason": None,
            },
            {
                "domain": "comp2",
                "title": "Test 2",
                "source": "bla2",
                "state": "setup_error",
                "supports_options": False,
                "supports_unload": False,
                "disabled_by": None,
                "reason": "Unsupported API",
            },
            {
                "domain": "comp3",
                "title": "Test 3",
                "source": "bla3",
                "state": "not_loaded",
                "supports_options": False,
                "supports_unload": False,
                "disabled_by": core_ce.DISABLED_USER,
                "reason": None,
            },
        ]


async def test_remove_entry(hass, client):
    """Test removing an entry via the API."""
    entry = MockConfigEntry(domain="demo", state=core_ce.ENTRY_STATE_LOADED)
    entry.add_to_hass(hass)
    resp = await client.delete(f"/api/config/config_entries/entry/{entry.entry_id}")
    assert resp.status == 200
    data = await resp.json()
    assert data == {"require_restart": True}
    assert len(hass.config_entries.async_entries()) == 0


async def test_reload_entry(hass, client):
    """Test reloading an entry via the API."""
    entry = MockConfigEntry(domain="demo", state=core_ce.ENTRY_STATE_LOADED)
    entry.add_to_hass(hass)
    resp = await client.post(
        f"/api/config/config_entries/entry/{entry.entry_id}/reload"
    )
    assert resp.status == 200
    data = await resp.json()
    assert data == {"require_restart": True}
    assert len(hass.config_entries.async_entries()) == 1


async def test_reload_invalid_entry(hass, client):
    """Test reloading an invalid entry via the API."""
    resp = await client.post("/api/config/config_entries/entry/invalid/reload")
    assert resp.status == 404


async def test_remove_entry_unauth(hass, client, hass_admin_user):
    """Test removing an entry via the API."""
    hass_admin_user.groups = []
    entry = MockConfigEntry(domain="demo", state=core_ce.ENTRY_STATE_LOADED)
    entry.add_to_hass(hass)
    resp = await client.delete(f"/api/config/config_entries/entry/{entry.entry_id}")
    assert resp.status == 401
    assert len(hass.config_entries.async_entries()) == 1


async def test_reload_entry_unauth(hass, client, hass_admin_user):
    """Test reloading an entry via the API."""
    hass_admin_user.groups = []
    entry = MockConfigEntry(domain="demo", state=core_ce.ENTRY_STATE_LOADED)
    entry.add_to_hass(hass)
    resp = await client.post(
        f"/api/config/config_entries/entry/{entry.entry_id}/reload"
    )
    assert resp.status == 401
    assert len(hass.config_entries.async_entries()) == 1


async def test_reload_entry_in_failed_state(hass, client, hass_admin_user):
    """Test reloading an entry via the API that has already failed to unload."""
    entry = MockConfigEntry(domain="demo", state=core_ce.ENTRY_STATE_FAILED_UNLOAD)
    entry.add_to_hass(hass)
    resp = await client.post(
        f"/api/config/config_entries/entry/{entry.entry_id}/reload"
    )
    assert resp.status == 403
    assert len(hass.config_entries.async_entries()) == 1


async def test_available_flows(hass, client):
    """Test querying the available flows."""
    with patch.object(config_flows, "FLOWS", ["hello", "world"]):
        resp = await client.get("/api/config/config_entries/flow_handlers")
        assert resp.status == 200
        data = await resp.json()
        assert set(data) == {"hello", "world"}


############################
#  FLOW MANAGER API TESTS  #
############################


async def test_initialize_flow(hass, client):
    """Test we can initialize a flow."""
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required("username")] = str
            schema[vol.Required("password")] = str

            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                description_placeholders={
                    "url": "https://example.com",
                    "show_advanced_options": self.show_advanced_options,
                },
                errors={"username": "Should be unique."},
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow",
            json={"handler": "test", "show_advanced_options": True},
        )

    assert resp.status == 200
    data = await resp.json()

    data.pop("flow_id")

    assert data == {
        "type": "form",
        "handler": "test",
        "step_id": "user",
        "data_schema": [
            {"name": "username", "required": True, "type": "string"},
            {"name": "password", "required": True, "type": "string"},
        ],
        "description_placeholders": {
            "url": "https://example.com",
            "show_advanced_options": True,
        },
        "errors": {"username": "Should be unique."},
        "last_step": None,
    }


async def test_initialize_flow_unauth(hass, client, hass_admin_user):
    """Test we can initialize a flow."""
    hass_admin_user.groups = []

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required("username")] = str
            schema[vol.Required("password")] = str

            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                description_placeholders={"url": "https://example.com"},
                errors={"username": "Should be unique."},
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == 401


async def test_abort(hass, client):
    """Test a flow that aborts."""
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            return self.async_abort(reason="bla")

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == 200
    data = await resp.json()
    data.pop("flow_id")
    assert data == {
        "description_placeholders": None,
        "handler": "test",
        "reason": "bla",
        "type": "abort",
    }


async def test_create_account(hass, client):
    """Test a flow that creates an account."""
    mock_entity_platform(hass, "config_flow.test", None)

    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            return self.async_create_entry(
                title="Test Entry", data={"secret": "account_token"}
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == 200

    entries = hass.config_entries.async_entries("test")
    assert len(entries) == 1

    data = await resp.json()
    data.pop("flow_id")
    assert data == {
        "handler": "test",
        "title": "Test Entry",
        "type": "create_entry",
        "version": 1,
        "result": {
            "disabled_by": None,
            "domain": "test",
            "entry_id": entries[0].entry_id,
            "source": core_ce.SOURCE_USER,
            "state": "loaded",
            "supports_options": False,
            "supports_unload": False,
            "title": "Test Entry",
            "reason": None,
        },
        "description": None,
        "description_placeholders": None,
        "options": {},
    }


async def test_two_step_flow(hass, client):
    """Test we can finish a two step flow."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            return self.async_show_form(
                step_id="account", data_schema=vol.Schema({"user_title": str})
            )

        async def async_step_account(self, user_input=None):
            return self.async_create_entry(
                title=user_input["user_title"], data={"secret": "account_token"}
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )
        assert resp.status == 200
        data = await resp.json()
        flow_id = data.pop("flow_id")
        assert data == {
            "type": "form",
            "handler": "test",
            "step_id": "account",
            "data_schema": [{"name": "user_title", "type": "string"}],
            "description_placeholders": None,
            "errors": None,
            "last_step": None,
        }

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            f"/api/config/config_entries/flow/{flow_id}",
            json={"user_title": "user-title"},
        )
        assert resp.status == 200

        entries = hass.config_entries.async_entries("test")
        assert len(entries) == 1

        data = await resp.json()
        data.pop("flow_id")
        assert data == {
            "handler": "test",
            "type": "create_entry",
            "title": "user-title",
            "version": 1,
            "result": {
                "disabled_by": None,
                "domain": "test",
                "entry_id": entries[0].entry_id,
                "source": core_ce.SOURCE_USER,
                "state": "loaded",
                "supports_options": False,
                "supports_unload": False,
                "title": "user-title",
                "reason": None,
            },
            "description": None,
            "description_placeholders": None,
            "options": {},
        }


async def test_continue_flow_unauth(hass, client, hass_admin_user):
    """Test we can't finish a two step flow."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            return self.async_show_form(
                step_id="account", data_schema=vol.Schema({"user_title": str})
            )

        async def async_step_account(self, user_input=None):
            return self.async_create_entry(
                title=user_input["user_title"], data={"secret": "account_token"}
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )
        assert resp.status == 200
        data = await resp.json()
        flow_id = data.pop("flow_id")
        assert data == {
            "type": "form",
            "handler": "test",
            "step_id": "account",
            "data_schema": [{"name": "user_title", "type": "string"}],
            "description_placeholders": None,
            "errors": None,
            "last_step": None,
        }

    hass_admin_user.groups = []

    resp = await client.post(
        f"/api/config/config_entries/flow/{flow_id}",
        json={"user_title": "user-title"},
    )
    assert resp.status == 401


async def test_get_progress_index(hass, hass_ws_client):
    """Test querying for the flows that are in progress."""
    assert await async_setup_component(hass, "config", {})
    mock_entity_platform(hass, "config_flow.test", None)
    ws_client = await hass_ws_client(hass)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 5

        async def async_step_hassio(self, info):
            return await self.async_step_account()

        async def async_step_account(self, user_input=None):
            return self.async_show_form(step_id="account")

    with patch.dict(HANDLERS, {"test": TestFlow}):
        form = await hass.config_entries.flow.async_init(
            "test", context={"source": core_ce.SOURCE_HASSIO}
        )

    await ws_client.send_json({"id": 5, "type": "config_entries/flow/progress"})
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == [
        {
            "flow_id": form["flow_id"],
            "handler": "test",
            "step_id": "account",
            "context": {"source": core_ce.SOURCE_HASSIO},
        }
    ]


async def test_get_progress_index_unauth(hass, hass_ws_client, hass_admin_user):
    """Test we can't get flows that are in progress."""
    assert await async_setup_component(hass, "config", {})
    hass_admin_user.groups = []
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 5, "type": "config_entries/flow/progress"})
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"


async def test_get_progress_flow(hass, client):
    """Test we can query the API for same result as we get from init a flow."""
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required("username")] = str
            schema[vol.Required("password")] = str

            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                errors={"username": "Should be unique."},
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == 200
    data = await resp.json()

    resp2 = await client.get(
        "/api/config/config_entries/flow/{}".format(data["flow_id"])
    )

    assert resp2.status == 200
    data2 = await resp2.json()

    assert data == data2


async def test_get_progress_flow_unauth(hass, client, hass_admin_user):
    """Test we can can't query the API for result of flow."""
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required("username")] = str
            schema[vol.Required("password")] = str

            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                errors={"username": "Should be unique."},
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == 200
    data = await resp.json()

    hass_admin_user.groups = []

    resp2 = await client.get(
        "/api/config/config_entries/flow/{}".format(data["flow_id"])
    )

    assert resp2.status == 401


async def test_options_flow(hass, client):
    """Test we can change options."""

    class TestFlow(core_ce.ConfigFlow):
        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            class OptionsFlowHandler(data_entry_flow.FlowHandler):
                async def async_step_init(self, user_input=None):
                    schema = OrderedDict()
                    schema[vol.Required("enabled")] = bool
                    return self.async_show_form(
                        step_id="user",
                        data_schema=schema,
                        description_placeholders={"enabled": "Set to true to be true"},
                    )

            return OptionsFlowHandler()

    MockConfigEntry(
        domain="test",
        entry_id="test1",
        source="bla",
    ).add_to_hass(hass)
    entry = hass.config_entries.async_entries()[0]

    with patch.dict(HANDLERS, {"test": TestFlow}):
        url = "/api/config/config_entries/options/flow"
        resp = await client.post(url, json={"handler": entry.entry_id})

    assert resp.status == 200
    data = await resp.json()

    data.pop("flow_id")
    assert data == {
        "type": "form",
        "handler": "test1",
        "step_id": "user",
        "data_schema": [{"name": "enabled", "required": True, "type": "boolean"}],
        "description_placeholders": {"enabled": "Set to true to be true"},
        "errors": None,
        "last_step": None,
    }


async def test_two_step_options_flow(hass, client):
    """Test we can finish a two step options flow."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )

    class TestFlow(core_ce.ConfigFlow):
        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            class OptionsFlowHandler(data_entry_flow.FlowHandler):
                async def async_step_init(self, user_input=None):
                    return self.async_show_form(
                        step_id="finish", data_schema=vol.Schema({"enabled": bool})
                    )

                async def async_step_finish(self, user_input=None):
                    return self.async_create_entry(
                        title="Enable disable", data=user_input
                    )

            return OptionsFlowHandler()

    MockConfigEntry(
        domain="test",
        entry_id="test1",
        source="bla",
    ).add_to_hass(hass)
    entry = hass.config_entries.async_entries()[0]

    with patch.dict(HANDLERS, {"test": TestFlow}):
        url = "/api/config/config_entries/options/flow"
        resp = await client.post(url, json={"handler": entry.entry_id})

        assert resp.status == 200
        data = await resp.json()
        flow_id = data.pop("flow_id")
        assert data == {
            "type": "form",
            "handler": "test1",
            "step_id": "finish",
            "data_schema": [{"name": "enabled", "type": "boolean"}],
            "description_placeholders": None,
            "errors": None,
            "last_step": None,
        }

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            f"/api/config/config_entries/options/flow/{flow_id}",
            json={"enabled": True},
        )
        assert resp.status == 200
        data = await resp.json()
        data.pop("flow_id")
        assert data == {
            "handler": "test1",
            "type": "create_entry",
            "title": "Enable disable",
            "version": 1,
            "description": None,
            "description_placeholders": None,
        }


async def test_list_system_options(hass, hass_ws_client):
    """Test that we can list an entries system options."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(domain="demo")
    entry.add_to_hass(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/system_options/list",
            "entry_id": entry.entry_id,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == {"disable_new_entities": False}


async def test_update_system_options(hass, hass_ws_client):
    """Test that we can update system options."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(domain="demo")
    entry.add_to_hass(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/system_options/update",
            "entry_id": entry.entry_id,
            "disable_new_entities": True,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"]["disable_new_entities"]
    assert entry.system_options.disable_new_entities


async def test_update_system_options_nonexisting(hass, hass_ws_client):
    """Test that we can update entry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/system_options/update",
            "entry_id": "non_existing",
            "disable_new_entities": True,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "not_found"


async def test_update_entry(hass, hass_ws_client):
    """Test that we can update entry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(domain="demo", title="Initial Title")
    entry.add_to_hass(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/update",
            "entry_id": entry.entry_id,
            "title": "Updated Title",
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"]["title"] == "Updated Title"
    assert entry.title == "Updated Title"


async def test_update_entry_nonexisting(hass, hass_ws_client):
    """Test that we can update entry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/update",
            "entry_id": "non_existing",
            "title": "Updated Title",
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "not_found"


async def test_disable_entry(hass, hass_ws_client):
    """Test that we can disable entry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(domain="demo", state="loaded")
    entry.add_to_hass(hass)
    assert entry.disabled_by is None

    # Disable
    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/disable",
            "entry_id": entry.entry_id,
            "disabled_by": core_ce.DISABLED_USER,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == {"require_restart": True}
    assert entry.disabled_by == core_ce.DISABLED_USER
    assert entry.state == "failed_unload"

    # Enable
    await ws_client.send_json(
        {
            "id": 6,
            "type": "config_entries/disable",
            "entry_id": entry.entry_id,
            "disabled_by": None,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == {"require_restart": True}
    assert entry.disabled_by is None
    assert entry.state == "failed_unload"

    # Enable again -> no op
    await ws_client.send_json(
        {
            "id": 7,
            "type": "config_entries/disable",
            "entry_id": entry.entry_id,
            "disabled_by": None,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == {"require_restart": False}
    assert entry.disabled_by is None
    assert entry.state == "failed_unload"


async def test_disable_entry_nonexisting(hass, hass_ws_client):
    """Test that we can disable entry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/disable",
            "entry_id": "non_existing",
            "disabled_by": core_ce.DISABLED_USER,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "not_found"


async def test_ignore_flow(hass, hass_ws_client):
    """Test we can ignore a flow."""
    assert await async_setup_component(hass, "config", {})
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            await self.async_set_unique_id("mock-unique-id")
            return self.async_show_form(step_id="account", data_schema=vol.Schema({}))

    ws_client = await hass_ws_client(hass)

    with patch.dict(HANDLERS, {"test": TestFlow}):
        result = await hass.config_entries.flow.async_init(
            "test", context={"source": core_ce.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        await ws_client.send_json(
            {
                "id": 5,
                "type": "config_entries/ignore_flow",
                "flow_id": result["flow_id"],
                "title": "Test Integration",
            }
        )
        response = await ws_client.receive_json()

        assert response["success"]

    assert len(hass.config_entries.flow.async_progress()) == 0

    entry = hass.config_entries.async_entries("test")[0]
    assert entry.source == "ignore"
    assert entry.unique_id == "mock-unique-id"
    assert entry.title == "Test Integration"


async def test_ignore_flow_nonexisting(hass, hass_ws_client):
    """Test we can ignore a flow."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/ignore_flow",
            "flow_id": "non_existing",
            "title": "Test Integration",
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "not_found"
