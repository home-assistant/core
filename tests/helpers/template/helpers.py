"""Helpers for tests around template rendering."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.typing import TemplateVarsType


def render(
    hass: HomeAssistant,
    template_str: str,
    variables: TemplateVarsType | None = None,
    **render_kwargs: Any,
) -> str:
    """Render template and return result."""
    return template.Template(template_str, hass).async_render(
        variables, **render_kwargs
    )


def render_to_info(
    hass: HomeAssistant, template_str: str, variables: TemplateVarsType | None = None
) -> template.RenderInfo:
    """Create render info from template."""
    return template.Template(template_str, hass).async_render_to_info(variables)


def extract_entities(
    hass: HomeAssistant, template_str: str, variables: TemplateVarsType | None = None
) -> set[str]:
    """Extract entities from a template."""
    return render_to_info(hass, template_str, variables).entities


def assert_result_info(
    info: template.RenderInfo,
    result: Any,
    entities: Iterable[str] | None = None,
    domains: Iterable[str] | None = None,
    all_states: bool = False,
) -> None:
    """Check result info."""
    assert info.result() == result
    assert info.all_states == all_states
    assert info.filter("invalid_entity_name.somewhere") == all_states
    if entities is not None:
        assert info.entities == frozenset(entities)
        assert all(info.filter(entity) for entity in entities)
        if not all_states:
            assert not info.filter("invalid_entity_name.somewhere")
    else:
        assert not info.entities
    if domains is not None:
        assert info.domains == frozenset(domains)
        assert all(info.filter(domain + ".entity") for domain in domains)
    else:
        assert not hasattr(info, "_domains")
