Status: DONE

Phase 13 fills in the 28 remaining domain proxy classes (plus a `scene`
symmetry proxy) under `homeassistant/components/sandbox_v2/entity/`, so
`_DOMAIN_PROXIES` now dispatches every supported HA entity domain to a
typed proxy. Each proxy subclasses `SandboxProxyEntity` + the domain's
`*Entity` and exposes the domain's typed properties out of
`_state_cache`, then translates each entity-method call into a
`sandbox_v2/call_service` RPC via the Phase-5 batcher + exception
translator. Domains that index `supported_features` with `in`
(`alarm_control_panel`, `climate`, `cover`, `fan`, `humidifier`,
`lawn_mower`, `lock`, `media_player`, `notify`, `remote`, `siren`,
`todo`, `update`, `vacuum`, `valve`, `water_heater`, `weather`) re-wrap
the wire int into the domain's `*EntityFeature` IntFlag in `__init__`,
matching the Phase-5 `light` pattern. Four entities whose `state`
property is marked `@final` and reads a name-mangled private field
(`button`, `event`, `notify`, `scene`) override `sandbox_apply_state`
to set the mangled attribute directly so the parent's `@final` getter
computes the right state from the sandbox-side push. A parametrised
smoke test covers every new domain — register a synthetic entity, push
state, invoke one method, assert the resulting RPC.

Files added:
- homeassistant/components/sandbox_v2/entity/alarm_control_panel.py
- homeassistant/components/sandbox_v2/entity/button.py
- homeassistant/components/sandbox_v2/entity/calendar.py
- homeassistant/components/sandbox_v2/entity/climate.py
- homeassistant/components/sandbox_v2/entity/cover.py
- homeassistant/components/sandbox_v2/entity/date.py
- homeassistant/components/sandbox_v2/entity/datetime.py
- homeassistant/components/sandbox_v2/entity/device_tracker.py
- homeassistant/components/sandbox_v2/entity/event.py
- homeassistant/components/sandbox_v2/entity/fan.py
- homeassistant/components/sandbox_v2/entity/humidifier.py
- homeassistant/components/sandbox_v2/entity/lawn_mower.py
- homeassistant/components/sandbox_v2/entity/lock.py
- homeassistant/components/sandbox_v2/entity/media_player.py
- homeassistant/components/sandbox_v2/entity/notify.py
- homeassistant/components/sandbox_v2/entity/number.py
- homeassistant/components/sandbox_v2/entity/remote.py
- homeassistant/components/sandbox_v2/entity/scene.py
- homeassistant/components/sandbox_v2/entity/select.py
- homeassistant/components/sandbox_v2/entity/siren.py
- homeassistant/components/sandbox_v2/entity/text.py
- homeassistant/components/sandbox_v2/entity/time.py
- homeassistant/components/sandbox_v2/entity/todo.py
- homeassistant/components/sandbox_v2/entity/update.py
- homeassistant/components/sandbox_v2/entity/vacuum.py
- homeassistant/components/sandbox_v2/entity/valve.py
- homeassistant/components/sandbox_v2/entity/water_heater.py
- homeassistant/components/sandbox_v2/entity/weather.py
- tests/components/sandbox_v2/test_phase13_proxies.py

Files changed:
- homeassistant/components/sandbox_v2/entity/__init__.py — extend
  `_build_registry()` so `_DOMAIN_PROXIES` dispatches all 32 supported
  domains.
- sandbox_v2/plan.md — tick Phase 13 checkboxes and add the
  one-paragraph summary block.

Core HA files modified (review surface):
None.

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` → 121 passed
  (28 new parametrised proxy smoke tests + 93 prior tests)
- `uv run pytest /home/paulus/dev/hass/core/sandbox_v2/hass_client/ -q`
  → 45 passed (no sandbox-side code touched)
- `uv run prek run --files <30 changed files>` → all passing
  (ruff check, ruff format, codespell, mypy, pylint)

Things to flag for the next phase:
- **`calendar` / `todo` listing is not proxied.** Both ship a proxy
  that translates the create/update/delete service methods, but
  `async_get_events` (calendar) and `todo_items` (todo) are
  server-side queries with shapes the `sandbox_v2/call_service`
  channel can't express. They return empty lists / None today. A
  separate query-shaped RPC is needed and was outside Phase 13's
  scope — flag for a Phase-14 or Phase-15 follow-up if the compat
  baseline reveals integrations that rely on these.
- **`weather.async_forecast_*` not proxied.** Same shape problem as
  above — forecasts are async methods returning lists of dicts. The
  proxy exposes `condition` + instantaneous attributes; forecast
  retrieval would need its own RPC pattern.
- **`update.async_skip` / `async_clear_skipped` not forwarded.** Both
  are `@final` on the base class and mutate a name-mangled
  `__skipped_version` field — not a service call. Phase 13 doesn't
  surface a way to drive these from main; if the compat sweep flags
  it, the fix is the same name-mangled-write pattern Phase 13 uses
  for `button` / `event` / `notify` / `scene`.
- **`device_tracker` ignores GPS fields.** The proxy subclasses
  `BaseTrackerEntity` to avoid `TrackerEntity.state_attributes`'s
  `@final` decoration, which means lat/lon/gps_accuracy currently
  ride only as raw state attributes. If a real GPS integration shows
  up in the Phase-15 sweep, the fix is to inherit from
  `TrackerEntity` and feed `_attr_latitude` / `_attr_longitude` /
  `_attr_location_accuracy` from the cache in `sandbox_apply_state`.
- **`climate.temperature_unit` defaults to °C.** The proxy reads it
  out of `description.capabilities["temperature_unit"]`, but the
  sandbox-side `EntityBridge._describe_entity` does not push that
  key today — Phase 6's capability bridge only forwards
  `entity.capability_attributes`, and `ClimateEntity` doesn't surface
  `temperature_unit` there. Integrations relying on °F will show
  wrong units on main. Fix is one extra key in the sandbox-side
  payload builder; flag for the same follow-up as the
  `data_schema` / service-schema serialisation work.
- **Phase 5's deferred 200-light area-call benchmark and full
  area-targeted test remain deferred** — Phase 13 only proves
  per-domain shape, not the multi-entity scale Phase 5 promised.
  Phase 14 (`5b-other`) already owns the benchmark.
