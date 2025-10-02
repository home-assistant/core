"""Test template context management for Home Assistant."""

from __future__ import annotations

import jinja2

from homeassistant.helpers.template.context import (
    TemplateContextManager,
    render_with_context,
    template_context_manager,
    template_cv,
)


def test_template_context_manager() -> None:
    """Test TemplateContextManager functionality."""
    cm = TemplateContextManager()

    # Test setting template
    cm.set_template("{{ test }}", "rendering")
    assert template_cv.get() == ("{{ test }}", "rendering")

    # Test context manager exit
    cm.__exit__(None, None, None)
    assert template_cv.get() is None


def test_template_context_manager_context() -> None:
    """Test TemplateContextManager as context manager."""
    cm = TemplateContextManager()

    with cm:
        cm.set_template("{{ test }}", "parsing")
        assert template_cv.get() == ("{{ test }}", "parsing")

    # Should be cleared after exit
    assert template_cv.get() is None


def test_global_template_context_manager() -> None:
    """Test global template context manager instance."""
    # Should be an instance of TemplateContextManager
    assert isinstance(template_context_manager, TemplateContextManager)

    # Test it works like any other context manager
    template_context_manager.set_template("{{ global_test }}", "testing")
    assert template_cv.get() == ("{{ global_test }}", "testing")

    template_context_manager.__exit__(None, None, None)
    assert template_cv.get() is None


def test_render_with_context() -> None:
    """Test render_with_context function."""
    # Create a simple template
    env = jinja2.Environment()
    template_obj = env.from_string("Hello {{ name }}!")

    # Test rendering with context tracking
    result = render_with_context("Hello {{ name }}!", template_obj, name="World")
    assert result == "Hello World!"

    # Context should be cleared after rendering
    assert template_cv.get() is None


def test_render_with_context_sets_context() -> None:
    """Test that render_with_context properly sets template context."""
    # Create a template that we can use to check context
    jinja2.Environment()

    # We'll use a custom template class to capture context during rendering
    context_during_render = []

    class MockTemplate:
        def render(self, **kwargs):
            # Capture the context during rendering
            context_during_render.append(template_cv.get())
            return "rendered"

    mock_template = MockTemplate()

    # Render with context
    result = render_with_context("{{ test_template }}", mock_template, test=True)

    assert result == "rendered"
    # Should have captured the context during rendering
    assert len(context_during_render) == 1
    assert context_during_render[0] == ("{{ test_template }}", "rendering")
    # Context should be cleared after rendering
    assert template_cv.get() is None
