"""Test the KNX entity suggestion API."""

from typing import Any, override
from unittest.mock import patch

from homeassistant.components.knx.storage.entity_suggestions.base import (
    SuggestionProvider,
)
from homeassistant.components.knx.storage.entity_suggestions.const import (
    EntitySuggestion,
    PlatformSuggestion,
    ProviderResult,
    SuggestedGroupAddress,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.typing import WebSocketGenerator


def _suggestion(
    suggestion_id: str,
    platform: Platform,
    group_id: str = "1.1.1",
    existing_entity_ids: list[str] | None = None,
) -> EntitySuggestion:
    """Build a suggestion as a provider would return it - id not yet prefixed."""
    return EntitySuggestion(
        id=suggestion_id,
        source=_StubProvider.provider_id,
        suggested_name=f"Entity {suggestion_id}",
        group_id=group_id,
        group_name="Device",
        secondary_info="Channel",
        platform_options=[platform.value],
        suggestions={
            platform.value: PlatformSuggestion(
                knx={"ga_switch": {"write": "1/2/3"}},
                matched_group_addresses=[
                    SuggestedGroupAddress(address="1/2/3", name="GA 1/2/3")
                ],
                unmatched_dpas=[],
            )
        },
        existing_entity_ids=existing_entity_ids or [],
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
                _suggestion("light", Platform.LIGHT),
                _suggestion("cover", Platform.COVER, group_id="1.1.2"),
                _suggestion(
                    "configured", Platform.LIGHT, existing_entity_ids=["light.existing"]
                ),
            ],
            hints={"state": "ok"},
        )


async def _get_suggestions(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, **filters: Any
) -> dict:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "knx/get_entity_suggestions"} | filters)
    res = await client.receive_json()
    assert res["success"], res
    return res["result"]


async def test_ws_get_entity_suggestions(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test suggestions of a provider are returned with their hints."""
    await knx.setup_integration()
    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [_StubProvider],
    ):
        result = await _get_suggestions(hass, hass_ws_client)

    # ids are prefixed with the provider id so they stay unique across providers
    assert [suggestion["id"] for suggestion in result["suggestions"]] == [
        "stub_light",
        "stub_cover",
        "stub_configured",
    ]
    assert result["providers"] == {"stub": {"state": "ok"}}


async def test_ws_get_entity_suggestions_without_providers(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test an empty result when no provider generates suggestions."""
    await knx.setup_integration()
    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [],
    ):
        result = await _get_suggestions(hass, hass_ws_client)

    assert result == {"suggestions": [], "providers": {}}


async def test_ws_get_entity_suggestions_filtered(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test narrowing down suggestions."""
    await knx.setup_integration()
    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [_StubProvider],
    ):
        by_platform = await _get_suggestions(
            hass, hass_ws_client, platform=Platform.COVER
        )
        by_group = await _get_suggestions(hass, hass_ws_client, group_id="1.1.1")
        unconfigured = await _get_suggestions(
            hass, hass_ws_client, include_configured=False
        )

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
