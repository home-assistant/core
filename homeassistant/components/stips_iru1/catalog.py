"""Compatibility wrapper for STIPS catalog helpers."""

from stips_api_bridge.catalog import (
    async_enrich_remote_model,
    async_fetch_catalog_devices,
    iter_device_host_candidates,
    iter_model_read_type_keys,
    iter_model_read_type_keys_union,
    model_has_ir_signals,
    model_read_name_or_id,
    normalize_device_ip,
    normalize_device_mac,
    normalize_device_online,
)

__all__ = [
    "normalize_device_ip",
    "normalize_device_mac",
    "normalize_device_online",
    "iter_device_host_candidates",
    "model_has_ir_signals",
    "iter_model_read_type_keys",
    "model_read_name_or_id",
    "iter_model_read_type_keys_union",
    "async_enrich_remote_model",
    "async_fetch_catalog_devices",
]
