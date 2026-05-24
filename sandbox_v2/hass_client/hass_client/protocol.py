"""Sandbox-side mirror of ``homeassistant.components.sandbox_v2.protocol``.

Kept as a stand-alone module to honour the project boundary: the HA Core
integration must not import from ``hass_client`` at integration-load time,
and ``hass_client`` does not pull from ``homeassistant.components.*``. The
two files speak the same wire protocol — see the docstring on the HA side
for the message catalogue.
"""

from typing import Final

# Main → Sandbox
MSG_ENTRY_SETUP: Final = "sandbox_v2/entry_setup"
MSG_ENTRY_UNLOAD: Final = "sandbox_v2/entry_unload"
MSG_CALL_SERVICE: Final = "sandbox_v2/call_service"
MSG_SHUTDOWN: Final = "sandbox_v2/shutdown"

# Sandbox → Main
MSG_REGISTER_ENTITY: Final = "sandbox_v2/register_entity"
MSG_UNREGISTER_ENTITY: Final = "sandbox_v2/unregister_entity"
MSG_STATE_CHANGED: Final = "sandbox_v2/state_changed"
MSG_REGISTER_SERVICE: Final = "sandbox_v2/register_service"
MSG_UNREGISTER_SERVICE: Final = "sandbox_v2/unregister_service"
MSG_FIRE_EVENT: Final = "sandbox_v2/fire_event"
MSG_STORE_LOAD: Final = "sandbox_v2/store_load"
MSG_STORE_SAVE: Final = "sandbox_v2/store_save"
MSG_STORE_REMOVE: Final = "sandbox_v2/store_remove"


__all__ = [
    "MSG_CALL_SERVICE",
    "MSG_ENTRY_SETUP",
    "MSG_ENTRY_UNLOAD",
    "MSG_FIRE_EVENT",
    "MSG_REGISTER_ENTITY",
    "MSG_REGISTER_SERVICE",
    "MSG_SHUTDOWN",
    "MSG_STATE_CHANGED",
    "MSG_STORE_LOAD",
    "MSG_STORE_REMOVE",
    "MSG_STORE_SAVE",
    "MSG_UNREGISTER_ENTITY",
    "MSG_UNREGISTER_SERVICE",
]
