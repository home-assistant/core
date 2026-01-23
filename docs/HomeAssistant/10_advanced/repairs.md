---
title: "Repairs"
---

Home Assistant keeps track of issues which should be brought to the user's attention. These issues can be created by integrations or by Home Assistant itself. Issues can either be fixable via a RepairsFlow or by linking to a website with information on how the user can solve it themselves.

## Creating an issue

```python
from homeassistant.helpers import issue_registry as ir

ir.async_create_issue(
    hass,
    DOMAIN,
    "manual_migration",
    breaks_in_ha_version="2022.9.0",
    is_fixable=False,
    severity=ir.IssueSeverity.ERROR,
    translation_key="manual_migration",
)
```

| Attribute |  Type    | Default | Description |
| --------- | -------- | ------- | ----------- |
| domain | string | | Domain raising the issue
| issue_id | string | | An identifier for the issue, must be unique within `domain`
| breaks_in_ha_version | string | `None` | The version in which the issue is breaking
| data | dict | `None` | Arbitrary data, not shown to the user
| is_fixable | boolean | | True if the issue can be automatically fixed
| is_persistent | boolean | | True if the issue should persists across restarts of Home Assistant
| issue_domain | string | `None` | Set by integrations creating issues on behalf of other integrations
| learn_more_url | string | `None` | URL where the user can find more details about an issue
| severity | IssueSeverity |  | Severity of the issue
| translation_key | str |  | Translation key with a brief explanation of the issue
| translation_placeholders | dict | `None` | Placeholders which will be injected in the translation

### Severity of an issue

To better understand which severity level to choose, see the list below.

| IssueSeverity | Description                                                        |
|---------------|--------------------------------------------------------------------|
| CRITICAL      | Considered reserved, only used for true panic                      |
| ERROR         | Something is currently broken and needs immediate attention        |
| WARNING       | Something breaks in the future (e.g., API shutdown) and needs attention |

## Fixing an issue

If an issue has the `is_fixable` issue set to `True`, the user will be allowed to fix the issue. An issue which is successfully fixed will be removed from the issue registry.
If an automatic repair is possible, it should be implemented using a RepairsFlow.

### Offering an automatic repair

Create a new platform file in your integration folder called `repairs.py` and add code according to the pattern below.


```python
from __future__ import annotations

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant


class Issue1RepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await (self.async_step_confirm())

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id == "issue_1":
        return Issue1RepairFlow()
```


## Issue life cycle

### Issue persistence

An issue will be kept in the issue registry until it's removed by the integration that created it or by the user [fixing](#fixing-an-issue) it.

The `is_persistent` flag controls if an issue should be shown to the user after a restart of Home Assistant:
- If the `is_persistent` flag is set on the issue, the issue will be shown again to the user after a restart. Use this for issues that can only be detected when they occur (update failed, unknown action in automation).
- If the `is_persistent` flag is not set on the issue, the issue will not be shown again to the user after a restart until it's created again by its integration. Use this for issues that can be checked for, like low disk space.

### Ignored issues

It's possible for the user to "ignore" issues. An ignored issue is ignored until it's explicitly deleted - either by the integration or by the user successfully walking through its [repair flow](#fixing-an-issue) - and then created again. Ignoring an issue takes effect across restarts of Home Assistant regardless of [issue persistence](#issue-persistence).

## Deleting an issue

Integrations typically don't need to delete issues, but it may be useful in some cases.

```python
from homeassistant.helpers import issue_registry as ir

ir.async_delete_issue(hass, DOMAIN, "manual_migration")
```

