"""Template context management for Home Assistant."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from contextvars import ContextVar
from types import TracebackType
from typing import Any, override

import jinja2

# Context variable for template string tracking
template_cv: ContextVar[tuple[str, str] | None] = ContextVar(
    "template_cv", default=None
)

entity_filter_cv: ContextVar[Callable[[str], bool] | None] = ContextVar(
    "entity_filter_cv", default=None
)


class TemplateContextManager(AbstractContextManager):
    """Context manager to store template being parsed or rendered in a ContextVar."""

    def set_template(self, template_str: str, action: str) -> None:
        """Store template being parsed/rendered to aid error handling."""
        template_cv.set((template_str, action))

    @override
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
    template_str: str,
    template: jinja2.Template,
    entity_filter: Callable[[str], bool] | None = None,
    /,
    **kwargs: Any,
) -> str:
    """Render the template with its string and entity filter in ContextVars."""
    with template_context_manager as cm:
        cm.set_template(template_str, "rendering")
        # Work scheduled during a filtered render inherits a copy of its context
        if entity_filter is None and entity_filter_cv.get() is None:
            return template.render(**kwargs)
        token = entity_filter_cv.set(entity_filter)
        try:
            return template.render(**kwargs)
        finally:
            entity_filter_cv.reset(token)
