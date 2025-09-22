"""Template context management for Home Assistant."""

from __future__ import annotations

from contextlib import AbstractContextManager
from contextvars import ContextVar
from types import TracebackType
from typing import Any

import jinja2

# Context variable for template string tracking
template_cv: ContextVar[tuple[str, str] | None] = ContextVar(
    "template_cv", default=None
)


class TemplateContextManager(AbstractContextManager):
    """Context manager to store template being parsed or rendered in a ContextVar."""

    def set_template(self, template_str: str, action: str) -> None:
        """Store template being parsed or rendered in a Contextvar to aid error handling."""
        template_cv.set((template_str, action))

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Raise any exception triggered within the runtime context."""
        template_cv.set(None)


# Global context manager instance
template_context_manager = TemplateContextManager()


def render_with_context(
    template_str: str, template: jinja2.Template, **kwargs: Any
) -> str:
    """Store template being rendered in a ContextVar to aid error handling."""
    with template_context_manager as cm:
        cm.set_template(template_str, "rendering")
        return template.render(**kwargs)
