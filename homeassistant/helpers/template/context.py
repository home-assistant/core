"""Template context management for Home Assistant."""

from contextlib import AbstractContextManager
from contextvars import ContextVar
from types import TracebackType
from typing import Any, override

import jinja2

# Context variable for template string tracking
template_cv: ContextVar[tuple[str, str] | None] = ContextVar(
    "template_cv", default=None
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
    template_str: str, template: jinja2.Template, **kwargs: Any
) -> str:
    """Store template being rendered in a ContextVar to aid error handling."""
    environment = template.environment
    template_globals = template.globals

    # A context never writes to its parent, but its dict methods need a real dict
    if kwargs or not isinstance(template_globals, dict):
        parent = {**template_globals, **kwargs}
    else:
        parent = template_globals

    context = environment.context_class(
        environment, parent, template.name, template.blocks
    )

    with template_context_manager as cm:
        cm.set_template(template_str, "rendering")
        try:
            return environment.concat(template.root_render_func(context))
        except Exception:  # noqa: BLE001
            # Re-raises with the traceback pointing at the template line
            environment.handle_exception()
