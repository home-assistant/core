# Implementation Updates

This update introduces significant internal improvements to the Home Assistant Todoist integration, focusing on SDK modernization and improved task handling behavior.

---

## Todoist Coordinator Enhancements

### Return Active & Completed Tasks

The Todoist data coordinator was updated to support fetching both **active and completed tasks** in a single unified call.

Previously, the integration only returned active items, which limited task management and post-completion automation logic.  
The new approach enables:

- Visibility into recently completed items  
- Better synchronization between Todoist and Home Assistant  
- Support for automations based on task completion (e.g., notifications, scripts, or reminders)

This change ensures more complete task state information is available to Home Assistant entities.

---

## Migration to Todoist SDK v3.x

### Full Module Refactor

The complete Todoist integration has been upgraded to use the **Todoist Python SDK v3.x**, replacing legacy API calls from previous versions.

Key benefits include:

- Updated request models aligned with current Todoist APIs  
- More consistent and structured task payloads  
- Better reliability and long-term support  
- Reduced manual REST handling  

All internal service calls, request builders, and response parsers have been updated to match the new SDK structure.

> **Note:** This upgrade required changing multiple internal modules, including task creation, state updates, and coordinator logic.

### High-Level Migration Points (v2.x → v3.x)

- Return type changes (list vs coroutine vs async generator)  
- Removed / replaced API methods (e.g., `close_task()` → `complete_task()`)  
- Modified `due` object structure and potential `None` handling  
- Updated Home Assistant service mappings to new SDK calls  
- Import path and module location changes  
- Asynchronous API patterns required (`await` and `async for`)  
- Lack of backward compatibility with v2.x integrations

---

## Integration Test Refactoring

### Updated Existing Test Suite

All previous integration tests were revised to reflect the new SDK call structure and updated task response format.

### Added New Test Scenarios

New test cases have been introduced to validate the expanded task return behavior:

- Tests for active tasks retrieval  
- Tests for completed tasks retrieval  
- Validation of mixed task responses from the Todoist API  
- Checks for error handling with unexpected response formats  

This ensures full coverage of the new feature set and helps maintain stability after the SDK upgrade.

The updated tests provide confidence that the integration correctly processes task states and remains stable across future changes.

---

## Todoist Priority Extension



- This repository contains an enhancement to the existing `Home Assistant Todoist integration`, adding support for displaying `task priorities` in both the backend entity attributes and the frontend Todo list UI.

- The goal of this extension is to improve task visibility and user awareness by mapping Todoist’s internal priority values to clear, human-readable labels.

---

## Feature Overview
### Added Priority Display for Todoist Tasks
Todoist represents task priority using numeric values (`1–4`). Home Assistant previously did not expose or display this information. This extension introduces:

- Priority mapping from numeric → human-readable labels
    - `1 → Low`
    - `2 → Medium`
    - `3 → High`
    - `4 → Urgent`

- Frontend rendering of the priority field in the Todo list card
- Backend attribute `priority` added to each Todo entity
- Safe handling of invalid, missing, or unexpected priority values
    - Mapped to `"Unknown"` instead of causing errors

This makes Todoist tasks more informative in the Home Assistant UI.

---

### Design Summary
### Backend Changes (Core Integration)
- Added a helper function `define_priority_level()` to translate Todoist priorities.
- Updated task attribute construction to include the new mapped priority label.
- Implemented defensive checks for invalid API data.
- Ensured compatibility with the generic Home Assistant `todo` platform.

### Frontend Changes (Lovelace UI)
- Updated the Todo list UI card to display the new `priority` attribute.
- Ensured rendering logic gracefully handles missing fields.

---

### Testing
### Unit Tests

Added new parametrized test coverage for:

- Valid priority values (1–4)
- Invalid/edge cases:  
- `0`, `5`, negative numbers, `None`, floats, strings
    - All map to `"Unknown"`

- Tests are located in: `tests/components/todoist/test\_todo.py`

**File  structure\[Modified]:**
- `homeassistant/components/todoist/`
    - `__init__.py`
    - `todoist.py`
- Other updated backend files
    - `tests/components/todoist/test\_todo.py`
- `frontend/src/panels/lovelace/cards/`
    - `hui-todo-list-card.ts`
        - modified for priority display

## Toddoist Label based browsing Backend Changes

### **Modified Files**

#### `homeassistant/components/todo/__init__.py`
- Updated `TodoItem` dataclass so `labels` is now a **list of strings**.
- Updated service schemas (`add_item`, `update_item`) to validate labels as **list[str]**.
- Normalized labels to list format on add/update.
- Updated API responses (`todo.get_items`) to output labels as lists.
- Updated update logic to preserve labels and handle label changes cleanly.

---

### Todoist Integration Changes

### **Modified Files**

#### 5. `homeassistant/components/todoist/todo.py`
- Todoist → HA Mapping:
  - Converts Todoist task labels into **list[str]** inside `TodoItem`.
- HA → Todoist Mapping:
  - Converts `TodoItem.labels` list back into Todoist API format.
- Ensured labels are sent during create/update calls to Todoist.
- Improved data consistency between Todoist API and Home Assistant.

---

### Test Updates

### **Modified Files**

#### `tests/components/todoist/test_todo.py`
- Updated all expected test results involving labels.
- Modified `make_api_task` usage to include label lists when appropriate.
- Updated add/update tests to assert:
  - `labels` field appears in returned items.
  - `labels` are passed to Todoist API calls.
- Updated existing test parametrizations to match new list-format label behavior.

---

### Summary of Functional Changes

#### What labels now support:
- Add labels when creating a task.
- Update labels on existing tasks.
- Store labels in Home Assistant as a **list**, not a string.
- Display labels in UI.
- New Labels panel for browsing tasks by label.
- Labels round-trip correctly between:
  - UI → HA Core → Todoist API → HA Core → UI.
- All tests updated to reflect new behavior.

---

### Summary of All Modified Files
frontend/src/data/todo.ts
frontend/src/panels/todo/dialog-todo-item-editor.ts
frontend/src/panels/todo/ha-panel-todo.ts
homeassistant/components/todo/init.py
homeassistant/components/todoist/todo.py
tests/components/todois t/test_todo.py

---