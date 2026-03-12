"""Constants for the HiVi Speaker integration."""

from __future__ import annotations

DOMAIN = "hivi_speaker"

DISCOVERY_UPDATED = "hivi_speaker_discovery_updated"
DEVICE_RELATION_CHANGED = "hivi_speaker_device_relation_changed"
SIGNAL_DEVICE_DISCOVERED = "hivi_speaker_signal_device_discovered"
SIGNAL_DEVICE_STATUS_UPDATED = "hivi_speaker_signal_device_status_updated"

DISCOVERY_BASE_INTERVAL = 300  # seconds
DEVICE_OFFLINE_THRESHOLD = 180  # seconds
