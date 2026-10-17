# Repairs platform

Platform exists as `homeassistant/components/<domain>/repairs.py`.

- **Actionable Issues Required**: All repair issues must be actionable for end users
- **Issue Content Requirements**:
  - Clearly explain what is happening
  - Provide specific steps users need to take to resolve the issue
  - Use friendly, helpful language
  - Include relevant context (device names, error details, etc.)
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
- Only create issues for problems users can potentially resolve
