"""Test the KNX entity suggestion API."""

from typing import Any, override
from unittest.mock import patch

import pytest

from homeassistant.components.knx.storage.entity_suggestions.base import (
    SuggestionProvider,
)
from homeassistant.components.knx.storage.entity_suggestions.const import (
    PlatformSuggestion,
    ProviderResult,
    ProviderSuggestion,
    SuggestedGroupAddress,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import KnxEntityGenerator, KnxSuggestionGetter
from .conftest import KNXTestKit

# an entity is created on this address to test duplicate reporting
CONFIGURED_ADDRESS = "1/2/5"


def _suggestion(
    suggestion_id: str,
    platform: Platform,
    address: str,
    group_id: str = "1.1.1",
) -> ProviderSuggestion:
    """Build a suggestion as a provider would return it."""
    return ProviderSuggestion(
        id=suggestion_id,
        suggested_name=f"Entity {suggestion_id}",
        group_id=group_id,
        group_name="Device",
        secondary_info="Channel",
        platform_options=[platform.value],
        suggestions={
            platform.value: PlatformSuggestion(
                knx={"ga_switch": {"write": address}},
                matched_group_addresses=[
                    SuggestedGroupAddress(address=address, name=f"GA {address}")
                ],
                unmatched=[],
            )
        },
        metadata={},
    )


class _StubProvider(SuggestionProvider):
    """Provider returning a fixed set of suggestions."""

    provider_id = "stub"

    @override
    async def async_get_suggestions(
        self, hass: HomeAssistant, knx: Any
    ) -> ProviderResult:
        """Return suggestions covering every filterable property."""
        return ProviderResult(
            suggestions=[
                _suggestion("light", Platform.LIGHT, "1/2/3"),
                _suggestion("cover", Platform.COVER, "1/2/4", group_id="1.1.2"),
                _suggestion("configured", Platform.LIGHT, CONFIGURED_ADDRESS),
            ],
            hints={"state": "ok"},
        )


def test_provider_requires_provider_id() -> None:
    """Test a provider without `provider_id` can not be instantiated."""

    class _IncompleteProvider(SuggestionProvider):
        @override
        async def async_get_suggestions(
            self, hass: HomeAssistant, knx: Any
        ) -> ProviderResult:
            return ProviderResult(suggestions=[], hints={})

    with pytest.raises(TypeError):
        _IncompleteProvider()  # type: ignore[abstract]


async def test_ws_get_entity_suggestions(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test suggestions of a provider are returned with their hints."""
    await knx.setup_integration()
    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [_StubProvider()],
    ):
        result = await get_entity_suggestions()

    # ids are prefixed with the provider id so they stay unique across providers
    assert [suggestion["id"] for suggestion in result["suggestions"]] == [
        "stub_light",
        "stub_cover",
        "stub_configured",
    ]
    assert result["providers"] == {"stub": {"state": "ok"}}
    assert all(s["source"] == "stub" for s in result["suggestions"])
    # no entity uses these addresses yet
    assert all(not s["existing_entity_ids"] for s in result["suggestions"])


async def test_ws_get_entity_suggestions_existing_entities(
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test entities using a suggested group address are reported centrally."""
    await knx.setup_integration()
    entity = await create_ui_entity(
        Platform.SWITCH, {"ga_switch": {"write": CONFIGURED_ADDRESS}}
    )
    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [_StubProvider()],
    ):
        result = await get_entity_suggestions()

    by_id = {suggestion["id"]: suggestion for suggestion in result["suggestions"]}
    assert by_id["stub_configured"]["existing_entity_ids"] == [entity.entity_id]
    assert by_id["stub_light"]["existing_entity_ids"] == []


async def test_ws_get_entity_suggestions_without_providers(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test an empty result when no provider generates suggestions."""
    await knx.setup_integration()
    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [],
    ):
        result = await get_entity_suggestions()

    assert result == {"suggestions": [], "providers": {}}


async def test_ws_get_entity_suggestions_filtered(
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test narrowing down suggestions."""
    await knx.setup_integration()
    await create_ui_entity(
        Platform.SWITCH, {"ga_switch": {"write": CONFIGURED_ADDRESS}}
    )
    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [_StubProvider()],
    ):
        by_platform = await get_entity_suggestions(platform=Platform.COVER)
        by_group = await get_entity_suggestions(group_id="1.1.1")
        unconfigured = await get_entity_suggestions(include_configured=False)

    assert [suggestion["id"] for suggestion in by_platform["suggestions"]] == [
        "stub_cover"
    ]
    # hints are reported no matter how narrow the filter is
    assert by_platform["providers"] == {"stub": {"state": "ok"}}

    assert [suggestion["id"] for suggestion in by_group["suggestions"]] == [
        "stub_light",
        "stub_configured",
    ]
    # suggestions whose group addresses are already used are dropped
    assert [suggestion["id"] for suggestion in unconfigured["suggestions"]] == [
        "stub_light",
        "stub_cover",
    ]
