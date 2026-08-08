"""Tests for repairs model.py."""

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from homeassistant.components.repairs import (
    DOMAIN,
    FlowType,
    RepairsFlow,
    RepairsFlowResult,
    repairs_flow_manager,
)
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.issue_registry as ir

from tests.common import (
    AsyncMock,
    Mock,
    MockConfigEntry,
    MockModule,
    async_setup_component,
    mock_config_flow,
    mock_integration,
    mock_platform,
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
        return MockFixFlowNextFlow()

    mock_platform(
        hass,
        "fake_integration.repairs",
        Mock(async_create_fix_flow=AsyncMock(wraps=async_create_fix_flow)),
    )


@contextmanager
def mock_core_config_flow() -> Iterator[None]:
    """Mock a config flow."""

    class CompConfigSubentryFlowHandler(ConfigSubentryFlow):
        """Config subentry flow."""

        async def async_step_reconfigure(self, user_input=None) -> SubentryFlowResult:
            return self.async_show_form(step_id="reconfigure")

    class CompOptionsFlowHandler(OptionsFlow):
        """Options flow."""

        async def async_step_init(self, user_input=None):
            return self.async_show_form(step_id="init")

    class CompConfigFlow(ConfigFlow):
        """Config flow with options and subentries flow."""

        async def async_step_user(self, user_input=None):
            return self.async_show_form(step_id="user")

        async def async_step_reconfigure(self, user_input=None):
            return self.async_show_form(step_id="reconfigure")

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry
        ) -> dict[str, type[ConfigSubentryFlow]]:
            return {"fake_subentry": CompConfigSubentryFlowHandler}

        @staticmethod
        @callback
        def async_get_options_flow(config_entry) -> CompOptionsFlowHandler:
            return CompOptionsFlowHandler()

    with mock_config_flow("comp", CompConfigFlow):
        yield


class MockFixFlowNextFlow(RepairsFlow):
    """Mock flow fix supporting `next_flow`."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""

        mock_integration(self.hass, MockModule("comp"))
        mock_platform(self.hass, "comp.config_flow", None)

        entries = self.hass.config_entries.async_entries("comp")
        assert len(entries) == 1
        mock_entry: MockConfigEntry = entries[0]

        with mock_core_config_flow():
            if self.issue_id == FlowType.OPTIONS_FLOW:
                next_flow = await self.hass.config_entries.options.async_init(
                    mock_entry.entry_id
                )
                return self.async_create_entry(
                    next_flow=(FlowType.OPTIONS_FLOW, next_flow["flow_id"]), data={}
                )
            # self.issue_id == "subentry_config_issue"
            assert len(mock_entry.subentries) == 1
            next_flow = await self.hass.config_entries.subentries.async_init(
                (mock_entry.entry_id, "fake_subentry"),
                context={
                    "entry_id": mock_entry.entry_id,
                    "subentry_id": list(mock_entry.subentries.keys())[0],
                    "source": SOURCE_RECONFIGURE,
                },
            )
            return self.async_create_entry(
                next_flow=(FlowType.CONFIG_SUBENTRIES_FLOW, next_flow["flow_id"]),
                data={},
            )


@pytest.mark.parametrize(
    ("flow_type", "ignore_translations_for_mock_domains"),
    [
        (FlowType.OPTIONS_FLOW, ["fake_integration"]),
        (FlowType.CONFIG_SUBENTRIES_FLOW, ["fake_integration"]),
    ],
)
async def test_fix_issue_next_flow(hass: HomeAssistant, flow_type: FlowType) -> None:
    """Test that that a repair flow can refer to an options flow."""
    assert await async_setup_component(hass, DOMAIN, {})

    mock_entry = MockConfigEntry(
        domain="comp",
        data={},
        subentries_data=[
            {
                "unique_id": "test_1",
                "title": "test 1",
                "subentry_type": "fake_subentry",
                "data": {},
            }
        ],
    )
    mock_entry.add_to_hass(hass)

    ir.async_create_issue(
        hass,
        issue_id=flow_type,
        domain="fake_integration",
        is_fixable=True,
        severity="error",
        translation_key="fake_key",
    )

    assert (repairs := repairs_flow_manager(hass))

    flow = await repairs.async_init("fake_integration", data={"issue_id": flow_type})

    next_flow_type, _ = flow["next_flow"]

    assert next_flow_type is flow_type
    assert mock_entry == flow["result"]
