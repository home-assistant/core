"""Sandbox v2 proxy for ``button`` entities."""

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import Context

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxButtonEntity(SandboxProxyEntity, ButtonEntity):
    """Proxy for a ``button`` entity in a sandbox."""

    def sandbox_apply_state(
        self,
        state: str | None,
        attributes: dict[str, Any],
        context: Context | None = None,
    ) -> None:
        """Forward sandbox state into ButtonEntity's last-pressed field.

        ``ButtonEntity.state`` is ``@final`` and reads the name-mangled
        ``__last_pressed_isoformat`` attribute. Setting the cache alone
        wouldn't surface as the state on main, so we update the private
        field directly before the framework recomputes state.
        """
        if state is not None:
            # pylint: disable-next=attribute-defined-outside-init
            self._ButtonEntity__last_pressed_isoformat = state
        super().sandbox_apply_state(state, attributes, context)

    async def async_press(self) -> None:
        """Forward press as a ``button.press`` service call."""
        await self._call_service("press")
