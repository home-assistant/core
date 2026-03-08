"""Test the repairs websocket API."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock

import orjson
import pytest
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.components.repairs.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    FlowType,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockUser,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from tests.typing import (
    ClientSessionGenerator,
    MockHAClientWebSocket,
    WebSocketGenerator,
)

DEFAULT_ISSUES = [
    {
        "breaks_in_ha_version": "2022.9",
        "domain": "fake_integration",
        "issue_id": "issue_1",
        "is_fixable": True,
        "learn_more_url": "https://theuselessweb.com",
        "severity": "error",
        "translation_key": "abc_123",
        "translation_placeholders": {"abc": "123"},
    }
]


async def create_issues(
    hass: HomeAssistant,
    ws_client: MockHAClientWebSocket,
    issues: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Create issues."""

    def api_issue(issue):
        excluded_keys = ("data",)
        return dict(
            {key: issue[key] for key in issue if key not in excluded_keys},
            created=ANY,
            dismissed_version=None,
            ignored=False,
            issue_domain=None,
        )

    if issues is None:
        issues = DEFAULT_ISSUES

    for issue in issues:
        ir.async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            data=issue.get("data"),
            is_fixable=issue["is_fixable"],
            is_persistent=False,
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": [api_issue(issue) for issue in issues]}

    return issues


EXPECTED_DATA = {
    "issue_1": None,
    "issue_2": {"blah": "bleh"},
    "abort_issue1": None,
    "create_entry_issue1": {"test": ANY},
}


class MockFixFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        assert self.issue_id in EXPECTED_DATA
        assert self.data == EXPECTED_DATA[self.issue_id]

        return await self.async_step_custom_step()

    async def async_step_custom_step(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle a custom_step step of a fix flow."""
        if user_input is not None:
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="custom_step", data_schema=vol.Schema({}))


class MockFixFlowAbort(RepairsFlow):
    """Handler for an issue fixing flow that aborts."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return self.async_abort(reason="not_given")


class MockFixFlowCreateEntry(RepairsFlow):
    """Handler for an issue fixing flow that creates an entry (fixes an issue)."""

    def __init__(
        self,
        init_step: str = SOURCE_RECONFIGURE,
        flow_type: str = FlowType.CONFIG_FLOW,
        invalid_next_flow: bool = False,
    ) -> None:
        """Initialize the flow."""
        super().__init__()
        self.test_step = init_step
        self.flow_type = flow_type
        self.invalid_next_flow = invalid_next_flow

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        if self.invalid_next_flow:
            return self.async_create_entry(
                data={},
                next_flow=(
                    self.flow_type,
                    "fake_flow_id",
                ),
            )

        async def mock_async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
            """Mock setup."""
            return True

        async_setup_entry = AsyncMock(return_value=True)
        mock_integration(
            self.hass,
            MockModule(
                "comp",
                async_setup=mock_async_setup,
                async_setup_entry=async_setup_entry,
            ),
        )
        mock_platform(self.hass, "comp.config_flow", None)

        class TestOptionsFlow(OptionsFlow):
            async def async_step_init(
                self, user_input: dict[str, Any] | None = None
            ) -> ConfigFlowResult:
                """Init options flow."""
                if user_input is not None:
                    return self.async_create_entry(reason="updated")
                return self.async_show_form(step_id="init", data_schema=vol.Schema({}))

            async def async_step_fake(
                self, user_input: dict[str, Any] | None = None
            ) -> ConfigFlowResult:
                """Init options flow."""
                if user_input is not None:
                    return self.async_create_entry(reason="fake")
                return self.async_show_form(step_id="fake", data_schema=vol.Schema({}))

        class TestSubentryFlow(ConfigSubentryFlow):
            async def async_step_reconfigure(
                self, user_input: dict[str, Any] | None = None
            ) -> SubentryFlowResult:
                if user_input is not None:
                    return await self.async_update_and_abort(
                        self._get_entry(), self._get_reconfigure_subentry()
                    )
                return self.async_show_form(
                    step_id="reconfigure", data_schema=vol.Schema({})
                )

            async def async_step_fake(
                self, user_input: dict[str, Any] | None = None
            ) -> ConfigFlowResult:
                """Handle a fake step."""
                if user_input is not None:
                    return self.async_update_and_abort(reason="fake")
                return self.async_show_form(step_id="fake", data_schema=vol.Schema({}))

        class TestFlow(config_entries.ConfigFlow):
            """Test flow."""

            @staticmethod
            @callback
            def async_get_options_flow(
                config_entry: ConfigEntry,
            ) -> TestOptionsFlow:
                """Create the options flow."""
                return TestOptionsFlow()

            @classmethod
            @callback
            def async_get_supported_subentry_types(
                cls, config_entry: ConfigEntry
            ) -> dict[str, type[ConfigSubentryFlow]]:
                """Return subentries supported by this integration."""
                return {"test_subentry": TestSubentryFlow}

            async def async_step_reconfigure(
                self, user_input: dict[str, Any] | None = None
            ) -> ConfigFlowResult:
                """Handle a reconfigure step."""
                if user_input is not None:
                    return self.async_update_and_abort(reason="updated")
                return self.async_show_form(
                    step_id="reconfigure", data_schema=vol.Schema({})
                )

            async def async_step_fake(
                self, user_input: dict[str, Any] | None = None
            ) -> ConfigFlowResult:
                """Handle a fake step."""
                if user_input is not None:
                    return self.async_update_and_abort(reason="fake")
                return self.async_show_form(step_id="fake", data_schema=vol.Schema({}))

        entries = self.hass.config_entries.async_entries("comp")
        assert len(entries) == 1
        mock_entry: MockConfigEntry = entries[0]
        subentries = mock_entry.subentries
        assert len(list(subentries.keys())) == 1
        mock_subentry_id = list(subentries.keys())[0]

        with mock_config_flow("comp", TestFlow):
            next_flow: ConfigFlowResult = (
                await mock_entry.start_reconfigure_flow(self.hass)
                if self.test_step == SOURCE_RECONFIGURE
                and self.flow_type
                in [FlowType.CONFIG_FLOW, "fake"]  # to allow "fake" flow_type
                else (
                    await self.hass.config_entries.flow.async_init(
                        "comp",
                        context={
                            "source": self.test_step,
                            "entry_id": mock_entry.entry_id,
                        },
                    )
                    if self.flow_type == FlowType.CONFIG_FLOW
                    else (
                        await self.hass.config_entries.options.async_init(
                            mock_entry.entry_id
                        )
                        if self.flow_type == FlowType.OPTIONS_FLOW
                        else (
                            await mock_entry.start_subentry_reconfigure_flow(
                                self.hass, mock_subentry_id
                            )
                            if self.test_step == SOURCE_RECONFIGURE
                            else await self.hass.config_entries.subentries.async_init(
                                (mock_entry.entry_id, "test_subentry"),
                                context={
                                    "source": self.test_step,
                                    "subentry_id": mock_subentry_id,
                                },
                            )
                        )
                    )
                )
            )
            return self.async_create_entry(
                data={},
                next_flow=(
                    self.flow_type,
                    next_flow["flow_id"],
                ),
            )


@pytest.fixture(autouse=True)
async def mock_repairs_integration(hass: HomeAssistant) -> None:
    """Mock a repairs integration."""
    hass.config.components.add("fake_integration")

    def async_create_fix_flow(
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> RepairsFlow:
        assert issue_id in EXPECTED_DATA
        assert data == EXPECTED_DATA[issue_id]

        if issue_id == "abort_issue1":
            return MockFixFlowAbort()
        if issue_id == "create_entry_issue1":
            if data["test"] == "next_flow":
                return MockFixFlowCreateEntry()
            if data["test"] == "invalid_source":
                return MockFixFlowCreateEntry(init_step="fake")
            if data["test"] == "invalid_flow_type":
                return MockFixFlowCreateEntry(flow_type="fake")
            if data["test"] == "invalid_next_flow":
                return MockFixFlowCreateEntry(invalid_next_flow=True)
            if data["test"] == FlowType.OPTIONS_FLOW:
                return MockFixFlowCreateEntry(flow_type=FlowType.OPTIONS_FLOW)
            if data["test"] == FlowType.CONFIG_SUBENTRIES_FLOW:
                return MockFixFlowCreateEntry(flow_type=FlowType.CONFIG_SUBENTRIES_FLOW)
            if data["test"] == f"{FlowType.CONFIG_SUBENTRIES_FLOW}_invalid_source":
                return MockFixFlowCreateEntry(
                    flow_type=FlowType.CONFIG_SUBENTRIES_FLOW, init_step="fake"
                )
        return MockFixFlow()

    mock_platform(
        hass,
        "fake_integration.repairs",
        Mock(async_create_fix_flow=AsyncMock(wraps=async_create_fix_flow)),
    )
    mock_platform(
        hass,
        "integration_without_repairs.repairs",
        Mock(spec=[]),
    )


@pytest.mark.parametrize("ignore_translations_for_mock_domains", ["fake_integration"])
async def test_dismiss_issue(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we can dismiss an issue."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    issues = await create_issues(hass, client)

    await client.send_json(
        {
            "id": 2,
            "type": "repairs/ignore_issue",
            "domain": "fake_integration",
            "issue_id": "no_such_issue",
            "ignore": True,
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]

    await client.send_json(
        {
            "id": 3,
            "type": "repairs/ignore_issue",
            "domain": "fake_integration",
            "issue_id": "issue_1",
            "ignore": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    await client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created=ANY,
                dismissed_version=ha_version,
                ignored=True,
                issue_domain=None,
            )
            for issue in issues
        ]
    }

    await client.send_json(
        {
            "id": 5,
            "type": "repairs/ignore_issue",
            "domain": "fake_integration",
            "issue_id": "issue_1",
            "ignore": False,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    await client.send_json({"id": 6, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created=ANY,
                dismissed_version=None,
                ignored=False,
                issue_domain=None,
            )
            for issue in issues
        ]
    }


@pytest.mark.parametrize("ignore_translations_for_mock_domains", ["fake_integration"])
async def test_fix_non_existing_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test trying to fix an issue that doesn't exist."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    issues = await create_issues(hass, ws_client)

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": "no_such_integration", "issue_id": "no_such_issue"}
    )

    assert resp.status != HTTPStatus.OK

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "no_such_issue"}
    )

    assert resp.status != HTTPStatus.OK

    await ws_client.send_json({"id": 3, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created=ANY,
                dismissed_version=None,
                ignored=False,
                issue_domain=None,
            )
            for issue in issues
        ]
    }


@pytest.mark.parametrize(
    (
        "domain",
        "step",
        "description_placeholders",
        "ignore_translations_for_mock_domains",
    ),
    [
        ("fake_integration", "custom_step", None, ["fake_integration"]),
        (
            "fake_integration_default_handler",
            "confirm",
            {"abc": "123"},
            ["fake_integration_default_handler"],
        ),
    ],
)
async def test_fix_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    domain,
    step,
    description_placeholders,
) -> None:
    """Test we can fix an issue."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    issues = [
        {
            **DEFAULT_ISSUES[0],
            "data": {"blah": "bleh"},
            "domain": domain,
            "issue_id": "issue_2",
        }
    ]
    await create_issues(hass, ws_client, issues=issues)

    url = "/api/repairs/issues/fix"
    resp = await client.post(url, json={"handler": domain, "issue_id": "issue_2"})

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == (
        {
            "data_schema": [],
            "description_placeholders": description_placeholders,
            "errors": None,
            "flow_id": ANY,
            "handler": domain,
            "last_step": None,
            "preview": None,
            "step_id": step,
            "type": "form",
        }
    )

    url = f"/api/repairs/issues/fix/{flow_id}"
    # Test we can get the status of the flow
    resp2 = await client.get(url)

    assert resp2.status == HTTPStatus.OK
    data2 = await resp2.json()

    assert data == data2

    resp = await client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == (
        {
            "description": None,
            "description_placeholders": None,
            "flow_id": flow_id,
            "handler": domain,
            "type": "create_entry",
        }
    )

    await ws_client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}


@pytest.mark.parametrize(
    (
        "test",
        "ignore_translations_for_mock_domains",
    ),
    [
        ("next_flow", ["fake_integration"]),
        ("invalid_source", ["fake_integration"]),
        ("invalid_flow_type", ["fake_integration"]),
        ("invalid_next_flow", ["fake_integration"]),
        (FlowType.OPTIONS_FLOW, ["fake_integration"]),
        (FlowType.CONFIG_SUBENTRIES_FLOW, ["fake_integration"]),
        (f"{FlowType.CONFIG_SUBENTRIES_FLOW}_invalid_source", ["fake_integration"]),
    ],
)
async def test_fix_issue_next_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    test,
) -> None:
    """Test we can fix an issue."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    issues = [
        {
            **DEFAULT_ISSUES[0],
            "data": {"test": test},
            "issue_id": "create_entry_issue1",
        },
    ]
    await create_issues(hass, ws_client, issues=issues)

    mock_entry = MockConfigEntry(
        domain="comp",
        data={},
        subentries_data=[
            ConfigSubentry(
                title="Mock Subentry",
                unique_id="mock_subentry1",
                subentry_type="test_subentry",
                data={},
            ).as_dict()
        ],
    )
    mock_entry.add_to_hass(hass)

    url = "/api/repairs/issues/fix"

    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "create_entry_issue1"}
    )

    data = await resp.json()
    if test == "next_flow":
        assert resp.status == HTTPStatus.OK

        next_flow = hass.config_entries.flow.async_get(data["next_flow"][1])

        assert data == (
            {
                "description_placeholders": None,
                "flow_id": ANY,
                "handler": "fake_integration",
                "description": None,
                "type": "create_entry",
                "result": orjson.loads(orjson.dumps(mock_entry.as_json_fragment)),
                "next_flow": ["config_flow", next_flow["flow_id"]],
            }
        )

        await ws_client.send_json({"id": 4, "type": "repairs/list_issues"})
        msg = await ws_client.receive_json()

        assert msg["success"]
        assert msg["result"] == {"issues": []}

    if test == "invalid_source":
        assert resp.status == HTTPStatus.BAD_REQUEST

        assert data == {"message": "Next flow must be a reconfigure flow"}

    if test == "invalid_flow_type":
        assert resp.status == HTTPStatus.BAD_REQUEST
        assert data == {"message": "Invalid next_flow type"}

    if test == "invalid_next_flow":
        assert resp.status == HTTPStatus.BAD_REQUEST
        assert data == {"message": "Unknown next flow: config_flow: fake_flow_id"}

    if test == FlowType.OPTIONS_FLOW:
        assert resp.status == HTTPStatus.OK

        next_flow = hass.config_entries.options.async_get(data["next_flow"][1])

        assert data == (
            {
                "description_placeholders": None,
                "flow_id": ANY,
                "handler": "fake_integration",
                "description": None,
                "type": "create_entry",
                "result": orjson.loads(orjson.dumps(mock_entry.as_json_fragment)),
                "next_flow": ["options_flow", next_flow["flow_id"]],
            }
        )

        await ws_client.send_json({"id": 4, "type": "repairs/list_issues"})
        msg = await ws_client.receive_json()

        assert msg["success"]
        assert msg["result"] == {"issues": []}

    if test == FlowType.CONFIG_SUBENTRIES_FLOW:
        assert resp.status == HTTPStatus.OK

        next_flow = hass.config_entries.subentries.async_get(data["next_flow"][1])

        assert data == (
            {
                "description_placeholders": None,
                "flow_id": ANY,
                "handler": "fake_integration",
                "description": None,
                "type": "create_entry",
                "result": orjson.loads(orjson.dumps(mock_entry.as_json_fragment)),
                "next_flow": [FlowType.CONFIG_SUBENTRIES_FLOW, next_flow["flow_id"]],
            }
        )

        await ws_client.send_json({"id": 4, "type": "repairs/list_issues"})
        msg = await ws_client.receive_json()

        assert msg["success"]
        assert msg["result"] == {"issues": []}

    if test == f"{FlowType.CONFIG_SUBENTRIES_FLOW}_invalid_source":
        assert resp.status == HTTPStatus.BAD_REQUEST

        assert data == {"message": "Next flow must be a reconfigure flow"}


async def test_fix_issue_unauth(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_admin_user: MockUser
) -> None:
    """Test we can't query the result if not authorized."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    hass_admin_user.groups = []

    client = await hass_client()

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "issue_1"}
    )

    assert resp.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize("ignore_translations_for_mock_domains", ["fake_integration"])
async def test_get_progress_unauth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test we can't fix an issue if not authorized."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await create_issues(hass, ws_client)

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "issue_1"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    flow_id = data["flow_id"]

    hass_admin_user.groups = []

    url = f"/api/repairs/issues/fix/{flow_id}"
    # Test we can't get the status of the flow
    resp = await client.get(url)
    assert resp.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize("ignore_translations_for_mock_domains", ["fake_integration"])
async def test_step_unauth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test we can't fix an issue if not authorized."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await create_issues(hass, ws_client)

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "issue_1"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    flow_id = data["flow_id"]

    hass_admin_user.groups = []

    url = f"/api/repairs/issues/fix/{flow_id}"
    # Test we can't get the status of the flow
    resp = await client.post(url)
    assert resp.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize("ignore_translations_for_mock_domains", ["test"])
@pytest.mark.freeze_time("2022-07-19 07:53:05")
async def test_list_issues(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can list issues."""

    # Add an inactive issue, this should not be exposed in the list
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "data": {
            "issues": [
                {
                    "created": "2022-07-19T09:41:13.746514+00:00",
                    "dismissed_version": None,
                    "domain": "test",
                    "is_persistent": False,
                    "issue_id": "issue_3_inactive",
                    "issue_domain": None,
                },
            ]
        },
    }

    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}

    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "domain": "test",
            "is_fixable": True,
            "issue_id": "issue_1",
            "issue_domain": None,
            "learn_more_url": "https://theuselessweb.com",
            "severity": "error",
            "translation_key": "abc_123",
            "translation_placeholders": {"abc": "123"},
        },
        {
            "breaks_in_ha_version": "2022.8",
            "domain": "test",
            "is_fixable": False,
            "issue_id": "issue_2",
            "issue_domain": None,
            "learn_more_url": "https://theuselessweb.com/abc",
            "severity": "other",
            "translation_key": "even_worse",
            "translation_placeholders": {"def": "456"},
        },
    ]

    for issue in issues:
        ir.async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            is_fixable=issue["is_fixable"],
            is_persistent=False,
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created="2022-07-19T07:53:05+00:00",
                dismissed_version=None,
                ignored=False,
            )
            for issue in issues
        ]
    }


@pytest.mark.parametrize("ignore_translations_for_mock_domains", ["fake_integration"])
async def test_fix_issue_aborted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can fix an issue."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await create_issues(
        hass,
        ws_client,
        issues=[
            {
                **DEFAULT_ISSUES[0],
                "domain": "fake_integration",
                "issue_id": "abort_issue1",
            }
        ],
    )

    await ws_client.send_json({"id": 3, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1

    first_issue = msg["result"]["issues"][0]

    assert first_issue["domain"] == "fake_integration"
    assert first_issue["issue_id"] == "abort_issue1"

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": "fake_integration", "issue_id": "abort_issue1"},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "abort",
        "flow_id": flow_id,
        "handler": "fake_integration",
        "reason": "not_given",
        "description_placeholders": None,
    }

    await ws_client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    assert msg["result"]["issues"][0] == first_issue


@pytest.mark.parametrize("ignore_translations_for_mock_domains", ["test"])
@pytest.mark.freeze_time("2022-07-19 07:53:05")
async def test_get_issue_data(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we can get issue data."""

    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "data": None,
            "domain": "test",
            "is_fixable": True,
            "issue_id": "issue_1",
            "issue_domain": None,
            "learn_more_url": "https://theuselessweb.com",
            "severity": "error",
            "translation_key": "abc_123",
            "translation_placeholders": {"abc": "123"},
        },
        {
            "breaks_in_ha_version": "2022.8",
            "data": {"key": "value"},
            "domain": "test",
            "is_fixable": False,
            "issue_id": "issue_2",
            "issue_domain": None,
            "learn_more_url": "https://theuselessweb.com/abc",
            "severity": "other",
            "translation_key": "even_worse",
            "translation_placeholders": {"def": "456"},
        },
    ]

    for issue in issues:
        ir.async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            data=issue["data"],
            is_fixable=issue["is_fixable"],
            is_persistent=False,
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await client.send_json_auto_id(
        {"type": "repairs/get_issue_data", "domain": "test", "issue_id": "issue_1"}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"issue_data": None}

    await client.send_json_auto_id(
        {"type": "repairs/get_issue_data", "domain": "test", "issue_id": "issue_2"}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"issue_data": {"key": "value"}}

    await client.send_json_auto_id(
        {"type": "repairs/get_issue_data", "domain": "test", "issue_id": "unknown"}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "unknown_issue",
        "message": "Issue 'unknown' not found",
    }
