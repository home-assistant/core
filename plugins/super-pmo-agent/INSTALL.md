# Install or update super-pmo-agent

The repository marketplace registers `super-pmo-agent` for repo-local discovery. To install or update the plugin in the current user's local Codex plugin marketplace, run:

```bash
plugins/super-pmo-agent/install.sh
```

The installer replaces the local plugin copy at `~/plugins/super-pmo-agent` with the repo version and creates or updates `~/.agents/plugins/marketplace.json` with:

- `policy.installation`: `INSTALLED_BY_DEFAULT`
- `policy.authentication`: `ON_USE`
- `category`: `Productivity`

Restart Codex after installation or update so plugin and skill discovery reloads.
