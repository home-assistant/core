# iBeacon #88111 implementation plan (whitelist-based)

## Goal and constraints
- Fix `home-assistant/core` issue `#88111`: stop iBeacon from creating unwanted devices/entities.
- Implement in a medium-sized scope.
- Keep production-code impact to **4 files** (within required 2-4).
- Use an explicit whitelist model, as requested by issue participants.

## Proposed behavior
- Add a new iBeacon options-list whitelist of allowed beacon IDs.
- Beacon ID format: `uuid_major_minor` (same shape as internal group id).
- If whitelist is empty: keep current behavior (backward compatible).
- If whitelist has entries: only allowlisted beacon IDs are processed for new device/entity creation and updates.
- Existing `Enable newly added entities` behavior stays intact and is validated against the new filter.

## Production files to change (4)
1. `homeassistant/components/ibeacon/const.py`
- Add constant for the new options key (for example `CONF_ALLOWED_BEACONS`).
- Add small helper constants/messages if needed for input parsing.

2. `homeassistant/components/ibeacon/config_flow.py`
- Extend options flow to manage whitelist entries.
- Validate UUID/major/minor input, normalize UUID, and store canonical `uuid_major_minor` strings.
- Preserve existing options-flow behavior for nameless UUID allowlist.

3. `homeassistant/components/ibeacon/coordinator.py`
- Load whitelist from entry options.
- Enforce whitelist check in `_async_update_ibeacon` before tracker creation/update flow.
- Keep filtering consistent for both unique-address and random-MAC handling.

4. `homeassistant/components/ibeacon/strings.json`
- Add user-facing labels/descriptions/errors for new whitelist form fields.

## Test files to update (not counted toward 2-4)
- `tests/components/ibeacon/test_config_flow.py`
- `tests/components/ibeacon/test_coordinator.py`

## Team split (2 implementers + 1 write-up)

### Implementer A: config/options and UX
**Owns files:**
- `homeassistant/components/ibeacon/const.py`
- `homeassistant/components/ibeacon/config_flow.py`
- `homeassistant/components/ibeacon/strings.json`
- `tests/components/ibeacon/test_config_flow.py`

**Tasks:**
1. Add new whitelist option key and options-flow fields.
2. Implement input validation and canonical storage format.
3. Add config-flow tests for add/remove/invalid input.
4. Run targeted tests for options flow.

**Definition of done:**
- Options UI supports adding/removing whitelist entries.
- Invalid values fail with clear errors.
- Tests pass for options-flow behavior.

### Implementer B: runtime filtering and coordinator logic
**Owns files:**
- `homeassistant/components/ibeacon/coordinator.py`
- `tests/components/ibeacon/test_coordinator.py`

**Tasks:**
1. Read whitelist option and cache as a set in coordinator.
2. Gate beacon processing with whitelist logic.
3. Ensure random-MAC and unique-address paths both obey the filter.
4. Add regression tests for:
   - non-allowlisted beacon ignored
   - allowlisted beacon still tracked/updated
   - empty whitelist preserves current behavior
   - interaction with `pref_disable_new_entities`

**Definition of done:**
- No new device/entity is created for non-allowlisted beacons when whitelist is populated.
- Existing expected tracking behavior remains stable.
- Coordinator tests pass.

### Writer: assignment write-up + PR narrative
**Owns files:**
- `writeup.md` (or final PDF source doc)
- PR description text in GitHub

**Tasks:**
1. Draft assignment items 9-12 in final wording.
2. Draft PR summary: problem, solution, why whitelist, and test evidence.
3. Record final changed-file list and reconcile with initial impact analysis.
4. Collect links/placeholders (issue URL, fork URL, PR URL, screenshots/log evidence if needed).

**Definition of done:**
- Write-up is submission-ready except for final URLs/names.
- PR description clearly explains behavior change and testing.

## Integration checkpoints
1. A opens PR/branch with options-flow + strings + tests.
2. B rebases onto A (or merges A), then adds coordinator logic + tests.
3. Team runs:
   - `source .venv/bin/activate`
   - `pytest tests/components/ibeacon/test_config_flow.py tests/components/ibeacon/test_coordinator.py`
4. Writer finalizes `writeup.md` using merged-file reality.

## Acceptance criteria
- Whitelist empty => no behavior regression.
- Whitelist populated => non-allowlisted beacons do not create new devices/entities.
- Allowlisted beacons continue normal tracking and updates.
- Changes remain within 2-4 production files.

## Risks and mitigation
- Risk: options-flow UX becomes too complex.
  - Mitigation: store canonical single-string IDs and keep one-step flow.
- Risk: random-MAC path bypasses filter.
  - Mitigation: enforce filter before branching to unique/random handlers and add explicit tests.
- Risk: regressions around existing settings.
  - Mitigation: preserve existing option keys and add interaction tests.
