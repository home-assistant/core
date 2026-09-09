---
on:
  push:
    branches:
      - gh-aw/switch-permissions
permissions:
  contents: read
  copilot-requests: write
safe-outputs:
  report-failure-as-issue: false
---

# Copilot organization billing smoke test

Call the `noop` tool with the message:
"Copilot organization authentication succeeded."