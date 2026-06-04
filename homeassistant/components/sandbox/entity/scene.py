"""Sandbox proxy for ``scene`` entities.

``scene`` is in ``ALWAYS_MAIN`` so the classifier never routes it to a
sandbox in practice. The proxy ships anyway for symmetry — the full
set is covered so a future classifier change doesn't surprise us.
"""

from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.core import Context

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxSceneEntity(SandboxProxyEntity, Scene):
    """Proxy for a ``scene`` entity in a sandbox."""

    def sandbox_apply_state(
        self,
        state: str | None,
        attributes: dict[str, Any],
        context: Context | None = None,
    ) -> None:
        """Mirror the sandbox-side last-activated timestamp."""
        if state is not None:
            # pylint: disable-next=attribute-defined-outside-init
            self._BaseScene__last_activated = state
        super().sandbox_apply_state(state, attributes, context)

    async def async_activate(self, **kwargs: Any) -> None:
        """Forward activate as ``scene.turn_on``."""
        await self._call_service("turn_on", **kwargs)
