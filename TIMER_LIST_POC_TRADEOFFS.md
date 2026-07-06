# Timer list POC — known trade-offs

This branch is a proof of concept that replaces `intent`'s hand-rolled,
in-memory voice-timer storage with real `timer_list` entities (one
auto-created per `assist_satellite` device). It intentionally cuts scope in
several places so the PR stays reviewable. These are called out here so
reviewers and whoever picks up follow-on work don't have to rediscover them.

## Dropped / deferred features

- **`conversation_command` timers are gone.** The old system supported
  device-less timers that ran a delayed conversation command instead of
  notifying a device. This doesn't fit the entity-per-device model and needs
  its own design; it was removed rather than shimmed in.
- **`mobile_app` timer support is broken.** `mobile_app` registers a device
  for timer push-notifications but has no `AssistSatelliteEntity`, so it
  never gets an auto-created `timer_list` entity. Starting a timer for a
  mobile_app device now raises `TimersNotSupportedError`. Its tests are
  marked `xfail` with the reason recorded inline
  (`tests/components/mobile_app/test_timers.py`). Fix: give mobile_app
  devices a `timer_list` entity the same way `assist_satellite` does.
- **No `cancel_all_timers` / `clear_finished_timers` services.** Removed from
  `timer_list`/`local_timer_list` earlier in this branch. Archived timers can
  only be removed individually or via the automatic retention limit below.

## Behavior changes from the old voice-timer system

- **Finish action is always "archive."** Timers no longer support
  remove-on-finish or auto-restart; every finished/cancelled timer is kept
  (as `finished`/`cancelled`) until removed.
- **Archived timers are capped at 10 per entity**, oldest evicted first, with
  no way to configure the limit.
- **`created_seconds` no longer grows.** In the old system, adding time to a
  timer past its original length grew the value reported to satellites as
  the timer's nominal duration. The new `TimerItem.duration` is fixed at
  creation, so `TimerInfo.created_seconds` (and the `total_seconds` field
  sent to esphome/wyoming satellites) reflects the *original* duration even
  after time is added.
- **Removing more time than remains skips the "updated" event.** The timer
  transitions straight to `finished`, matching `LocalTimerListEntity`'s
  existing behavior, rather than emitting an intermediate zero-duration
  update before finishing (as the old system did).

## Design shortcuts

- **Auto-created timer list entities aren't linked to their device.** They
  show up as standalone entities named `"{device name} Timers"` rather than
  nested under the satellite's device in the UI (no `DeviceInfo` set). Purely
  cosmetic; the lookup logic doesn't depend on device linkage and this can be
  added later.
- **Auto-created vs. user-created entities are told apart implicitly.**
  Both live in the `timer_list` domain; the code distinguishes "this is a
  satellite's auto-created list" from "this is a user's `local_timer_list`
  helper" purely by the entity registry's `platform` field (`"timer_list"`
  vs. `"local_timer_list"`). There's no explicit flag — if that convention
  ever changes, voice matching (`_all_timer_infos` in
  `homeassistant/components/intent/timers.py`) silently stops seeing the
  right entities.
- **No cleanup of orphaned timer list entities.** If a satellite device is
  removed and re-added with a new device ID, its old `timer_list` entity
  (keyed by the old device ID) is never cleaned up.
- **New always-on dependency edges.** `intent` (a `system`-type integration,
  always loaded) now depends on `timer_list`, so `timer_list.async_setup`
  (services + websocket commands, no entities) runs on every Home Assistant
  install regardless of whether voice timers are used. `assist_satellite`
  now depends on `local_timer_list`.
- **No user-facing control over the auto-created lists** — no config entry,
  options flow, or way to opt a satellite out of getting one.
