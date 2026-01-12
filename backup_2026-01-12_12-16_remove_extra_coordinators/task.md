# Task: Address PR Review Feedback - Remove Extra Coordinators

## Objective
Address joostlek's PR review feedback on #160491 by keeping only the `core` coordinator and removing all others for now.

## Tasks

### Planning
- [x] Read PR review comments from joostlek
- [x] Review Withings integration architecture as reference
- [x] Create backups of all files to be modified
- [x] Create implementation plan

### Implementation
- [x] Simplify `coordinator.py` - keep only `CoreCoordinator` and `BaseGarminCoordinator`
- [x] Simplify `__init__.py` - use only `CoreCoordinator`
- [x] Move sensor descriptions from `sensor_descriptions.py` into `sensor.py` (Withings pattern)
- [x] Keep only `CORE` sensors, remove other coordinator types
- [x] Update `sensor.py` to use simplified architecture
- [x] Fix code quality issues (specific exceptions, no log-and-raise, etc.)
- [x] Services.py kept as-is (still works with client directly)
- [x] Update `strings.json` to remove unused translations (removed 50 keys)

### Verification
- [x] Run type checking (mypy) - PASSED (7 source files)
- [x] Run linting (ruff) - PASSED
- [ ] Run tests - needs test deps
- [ ] Test integration manually

## Files Changed
- `coordinator.py` - Kept only CoreCoordinator (110 lines vs 313)
- `__init__.py` - Simplified setup (109 lines vs 136)
- `sensor.py` - Combined with sensor descriptions (925 lines)
- `sensor_descriptions.py` - DELETED (content moved to sensor.py)
- `strings.json` - Removed 50 unused translation keys
