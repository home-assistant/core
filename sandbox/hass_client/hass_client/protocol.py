"""Sandbox-side mirror of ``homeassistant.components.sandbox.protocol``.

Kept as a stand-alone module to honour the project boundary: the HA Core
integration must not import from ``hass_client`` at integration-load time,
and ``hass_client`` does not pull from ``homeassistant.components.*``. The
two files speak the same wire protocol — see the docstring on the HA side
for the message catalogue.
"""

from typing import Final

# Handshake: the runtime's first frame on the channel. Replaces the old
# stdout text marker — the manager waits for this push instead of scanning
# stdout, so stdout carries nothing but channel frames.
MSG_READY: Final = "sandbox/ready"

# Main → Sandbox
MSG_ENTRY_SETUP: Final = "sandbox/entry_setup"
MSG_ENTRY_UNLOAD: Final = "sandbox/entry_unload"
MSG_CALL_SERVICE: Final = "sandbox/call_service"
MSG_ENTITY_QUERY: Final = "sandbox/entity_query"
MSG_GET_TRANSLATIONS: Final = "sandbox/get_translations"
MSG_SHUTDOWN: Final = "sandbox/shutdown"

# Sandbox → Main
MSG_REGISTER_ENTITY: Final = "sandbox/register_entity"
MSG_UNREGISTER_ENTITY: Final = "sandbox/unregister_entity"
MSG_STATE_CHANGED: Final = "sandbox/state_changed"
MSG_REGISTER_SERVICE: Final = "sandbox/register_service"
MSG_UNREGISTER_SERVICE: Final = "sandbox/unregister_service"
MSG_FIRE_EVENT: Final = "sandbox/fire_event"
MSG_STORE_LOAD: Final = "sandbox/store_load"
MSG_STORE_SAVE: Final = "sandbox/store_save"
MSG_STORE_REMOVE: Final = "sandbox/store_remove"


__all__ = [
    "MSG_CALL_SERVICE",
    "MSG_ENTITY_QUERY",
    "MSG_ENTRY_SETUP",
    "MSG_ENTRY_UNLOAD",
    "MSG_FIRE_EVENT",
    "MSG_GET_TRANSLATIONS",
    "MSG_READY",
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
