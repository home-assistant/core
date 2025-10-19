"""Test template render information tracking for Home Assistant."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.helpers.template.render_info import (
    ALL_STATES_RATE_LIMIT,
    DOMAIN_STATES_RATE_LIMIT,
    RenderInfo,
    _false,
    _true,
    render_info_cv,
)


@pytest.fixture
def template_obj(hass: HomeAssistant) -> template.Template:
    """Template object for test_render_info."""
    return template.Template("{{ 1 + 1 }}", hass)


def test_render_info_initialization(template_obj: template.Template) -> None:
    """Test RenderInfo initialization."""
    info = RenderInfo(template_obj)

    assert info.template is template_obj
    assert info._result is None
    assert info.is_static is False
    assert info.exception is None
    assert info.all_states is False
    assert info.all_states_lifecycle is False
    assert info.domains == set()
    assert info.domains_lifecycle == set()
    assert info.entities == set()
    assert info.rate_limit is None
    assert info.has_time is False
    assert info.filter_lifecycle is _true
    assert info.filter is _true


def test_render_info_repr(template_obj: template.Template) -> None:
    """Test RenderInfo representation."""
    info = RenderInfo(template_obj)
    info.domains.add("sensor")
    info.entities.add("sensor.test")

    repr_str = repr(info)
    assert "RenderInfo" in repr_str
    assert "domains={'sensor'}" in repr_str
    assert "entities={'sensor.test'}" in repr_str


def test_render_info_result(template_obj: template.Template) -> None:
    """Test RenderInfo result property."""
    info = RenderInfo(template_obj)

    # Test with no result set - should return None cast as str
    assert info.result() is None

    # Test with result set
    info._result = "test_result"
    assert info.result() == "test_result"

    # Test with exception
    info.exception = TemplateError("Test error")
    with pytest.raises(TemplateError, match="Test error"):
        info.result()


def test_render_info_filter_domains_and_entities(
    template_obj: template.Template,
) -> None:
    """Test RenderInfo entity and domain filtering."""
    info = RenderInfo(template_obj)

    # Add domain and entity
    info.domains.add("sensor")
    info.entities.add("light.test")

    # Should match domain
    assert info._filter_domains_and_entities("sensor.temperature") is True
    # Should match entity
    assert info._filter_domains_and_entities("light.test") is True
    # Should not match
    assert info._filter_domains_and_entities("switch.kitchen") is False


def test_render_info_filter_entities(template_obj: template.Template) -> None:
    """Test RenderInfo entity-only filtering."""
    info = RenderInfo(template_obj)

    info.entities.add("sensor.test")

    assert info._filter_entities("sensor.test") is True
    assert info._filter_entities("sensor.other") is False


def test_render_info_filter_lifecycle_domains(template_obj: template.Template) -> None:
    """Test RenderInfo domain lifecycle filtering."""
    info = RenderInfo(template_obj)

    info.domains_lifecycle.add("sensor")

    assert info._filter_lifecycle_domains("sensor.test") is True
    assert info._filter_lifecycle_domains("light.test") is False


def test_render_info_freeze_static(template_obj: template.Template) -> None:
    """Test RenderInfo static freezing."""
    info = RenderInfo(template_obj)

    info.domains.add("sensor")
    info.entities.add("sensor.test")
    info.all_states = True

    info._freeze_static()

    assert info.is_static is True
    assert info.all_states is False
    assert isinstance(info.domains, frozenset)
    assert isinstance(info.entities, frozenset)


def test_render_info_freeze(template_obj: template.Template) -> None:
    """Test RenderInfo freezing with rate limits."""
    info = RenderInfo(template_obj)

    # Test all_states rate limit
    info.all_states = True
    info._freeze()
    assert info.rate_limit == ALL_STATES_RATE_LIMIT

    # Test domain rate limit
    info = RenderInfo(template_obj)
    info.domains.add("sensor")
    info._freeze()
    assert info.rate_limit == DOMAIN_STATES_RATE_LIMIT

    # Test exception rate limit
    info = RenderInfo(template_obj)
    info.exception = TemplateError("Test")
    info._freeze()
    assert info.rate_limit == ALL_STATES_RATE_LIMIT


def test_render_info_freeze_filters(template_obj: template.Template) -> None:
    """Test RenderInfo filter assignment during freeze."""

    # Test lifecycle filter assignment
    info = RenderInfo(template_obj)
    info.domains_lifecycle.add("sensor")
    info._freeze()
    assert info.filter_lifecycle == info._filter_lifecycle_domains

    # Test no lifecycle domains
    info = RenderInfo(template_obj)
    info._freeze()
    assert info.filter_lifecycle is _false

    # Test domain and entity filter
    info = RenderInfo(template_obj)
    info.domains.add("sensor")
    info._freeze()
    assert info.filter == info._filter_domains_and_entities

    # Test entity-only filter
    info = RenderInfo(template_obj)
    info.entities.add("sensor.test")
    info._freeze()
    assert info.filter == info._filter_entities

    # Test no domains or entities
    info = RenderInfo(template_obj)
    info._freeze()
    assert info.filter is _false


def test_render_info_context_var(template_obj: template.Template) -> None:
    """Test render_info_cv context variable."""
    # Should start as None
    assert render_info_cv.get() is None

    # Test setting and getting
    info = RenderInfo(template_obj)
    render_info_cv.set(info)
    assert render_info_cv.get() is info

    # Reset for other tests
    render_info_cv.set(None)
    assert render_info_cv.get() is None
