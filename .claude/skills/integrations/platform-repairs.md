# Repairs platform

Platform exists as `homeassistant/components/<domain>/repairs.py`.

- **Actionable Issues Required**: All repair issues must be actionable for end users
- **Issue Content Requirements**:
  - Clearly explain what is happening
  - Provide specific steps users need to take to resolve the issue
  - Use friendly, helpful language
  - Include relevant context (device names, error details, etc.)
- **Implementation**:
  ```python
  ir.async_create_issue(
      hass,
      DOMAIN,
      "outdated_version",
      is_fixable=False,
      issue_domain=DOMAIN,
      severity=ir.IssueSeverity.ERROR,
      translation_key="outdated_version",
  )
  ```
- **Translation Strings Requirements**: Must contain user-actionable text in `strings.json`:
  ```json
  {
    "issues": {
      "outdated_version": {
        "title": "Device firmware is outdated",
        "description": "Your device firmware version {current_version} is below the minimum required version {min_version}. To fix this issue: 1) Open the manufacturer's mobile app, 2) Navigate to device settings, 3) Select 'Update Firmware', 4) Wait for the update to complete, then 5) Restart Home Assistant."
      }
    }
  }
  ```
- **String Content Must Include**:
  - What the problem is
  - Why it matters
  - Exact steps to resolve (numbered list when multiple steps)
  - What to expect after following the steps
- **Avoid Vague Instructions**: Don't just say "update firmware" - provide specific steps
- **Severity Guidelines**:
  - `CRITICAL`: Reserved for extreme scenarios only
  - `ERROR`: Requires immediate user attention
  - `WARNING`: Indicates future potential breakage
- **Additional Attributes**:
  ```python
  ir.async_create_issue(
      hass, DOMAIN, "issue_id",
      breaks_in_ha_version="2024.1.0",
      is_fixable=True,
      is_persistent=True,
      severity=ir.IssueSeverity.ERROR,
      translation_key="issue_description",
  )
  ```
- Only create issues for problems users can potentially resolve
