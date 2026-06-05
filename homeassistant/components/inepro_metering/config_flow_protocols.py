"""Typing helpers for split Inepro Metering config-flow mixins."""

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:

    class IneproFlowProtocol(Protocol):
        """Loose flow surface shared across mixin modules during type checking."""

        def __getattr__(self, name: str) -> Any:
            """Allow sibling mixins to expose the shared flow surface to mypy."""
            raise AttributeError(name)

else:
    # Multiple inheritance with Protocol classes is only needed by mypy.
    IneproFlowProtocol = object
