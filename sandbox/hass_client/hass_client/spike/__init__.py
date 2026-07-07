"""Phase 1 entity-bridge spike.

Two protocols are implemented in parallel:

- :mod:`hass_client.spike.bridge_a` — Option A, custom method-forward RPC.
- :mod:`hass_client.spike.bridge_b` — Option B, action-call forwarding.

Both sit on top of :mod:`hass_client.spike.transport`, an in-process JSON
transport that mimics a websocket so the comparison isolates protocol shape
from transport cost. :mod:`hass_client.spike.rig` builds a two-HA test bed
with N synthetic lights wired through whichever bridge is being measured.
"""
