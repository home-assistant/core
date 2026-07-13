# Install super-pmo-agent

The repository marketplace registers `super-pmo-agent` for repo-local discovery. To install the plugin into the current user's local Codex plugin marketplace, run:

```bash
plugins/super-pmo-agent/install.sh
```

The installer copies this plugin to `~/plugins/super-pmo-agent` and creates or updates `~/.agents/plugins/marketplace.json` with:

- `policy.installation`: `INSTALLED_BY_DEFAULT`
- `policy.authentication`: `ON_USE`
- `category`: `Productivity`

Restart Codex after installation so plugin and skill discovery reloads.
