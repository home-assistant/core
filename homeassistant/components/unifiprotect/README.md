# UniFi Protect Integration

This document covers details that new contributors may find helpful when
getting started.

## Thin integration on top of uiprotect

All communication with the console and devices goes through the
[`uiprotect`](https://github.com/uilibs/uiprotect) library; the integration
makes no direct API calls. If a capability is missing, it is added to
`uiprotect` first rather than worked around here.

The integration is push-based (`iot_class: local_push`): entity state is driven
by the WebSocket dispatcher in `data.py`. Avoid introducing polling.

## Entities are declarative

Entities are defined by `ProtectEntityDescription` tuples grouped per device
family (camera, light, sensor, chime, …). The `ufp_*` hooks map a device
attribute to the entity — e.g. `ufp_value` / `ufp_value_fn` for the value,
`ufp_required_field` / `ufp_enabled` for availability, and `ufp_set_method` /
`ufp_set_method_fn` for writes. Add a new entity by adding a description, not a
bespoke entity class. See `entity.py` for the full set.

## Public API migration

The integration is migrating to the UniFi Protect **Public Integration API**.
The older private API is considered legacy and is being phased out, so new
functionality should target the public API surfaced by `uiprotect`.

## Quality scale

This is a `platinum` integration; new code is expected to keep that bar (strict
typing, `has-entity-name`, `runtime-data`, `parallel-updates`, …). See
`quality_scale.yaml` for the tracked rules.

## Entity stability

Preserve entity `unique_id`s — changing them orphans users' history and
customizations.

## Tests

Tests are fixture- and snapshot-driven (Syrupy `.ambr`). After changing
`strings.json`, regenerate the translations or entity-name assertions fail:

    python3 -m script.translations develop --integration unifiprotect

## Contributing

This integration is actively migrating to the public API, so things are in
flux. If you're planning a larger change, it can be worth opening an issue
first to check it lines up with the current direction — it may save some
rework.
