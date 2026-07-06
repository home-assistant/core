# Overkiz Somfy multi-account support — design

_Date: 2026-07-06_

## Goal

Add support for Somfy "multi account sign-in" (one Somfy account spanning
multiple homes/sites) to the Home Assistant Overkiz integration, backed by the
`feat/somfy-multi-account` branch of `python-overkiz-api`.

The library adds a new region-agnostic server, `Server.SOMFY`, that:

1. Logs in with username/password (Somfy Accounts password grant → Keycloak
   token exchange).
2. Discovers **every site (home)** on the account via the Somfy BOB
   back-office directory (`discover_gateways()`), resolving the correct
   regional Overkiz endpoint per site.
3. Scopes the client to a chosen site (`select_gateway()`), auto-selecting when
   the account owns a single site.
4. Exposes a **resumable session**: after a site is selected,
   `client.to_credentials()` snapshots the session as `SomfyTokenCredentials`
   (a site-scoped, rotating refresh token plus `site_oid`, `region`,
   `gateway_id`). Passing these back on a later run logs in with no password
   grant, token exchange, or discovery.

This structurally mirrors the existing **Rexel** flow already in the
integration (`discover_gateways` → `select_gateway` → single-vs-multi), but
authenticates with username/password instead of OAuth2 and persists a refresh
token instead of an OAuth2 token bundle.

`Server.SOMFY` is already present in the library's `SUPPORTED_SERVERS`
(so it appears in the server picker automatically) and is **not** in
`SERVERS_WITH_LOCAL_API` (cloud-only).

## Credential storage decision

**Token only (plus email).** The config entry stores the resumable token bundle
and the account email; **no password** is written to disk. The email is an
identifier, not a secret — storing it lets reauth pre-fill the username field
(useful when one person has several Somfy accounts), matching the standard HA
cloud-flow pattern.

- Fast setup/reload: the token path skips the password grant, token exchange,
  and site discovery entirely.
- The Ginaite refresh token **rotates on every use**. While HA runs, the 30s
  coordinator poll keeps it alive indefinitely. After extended downtime the
  server-side refresh token may expire; recovery is a standard reauth prompt.
- On `ConfigEntryAuthFailed`, reauth re-prompts username/password, re-logs in,
  re-discovers, matches the existing gateway id, and stores a fresh token
  bundle.

## Config entry data

| Key | Value |
|---|---|
| `CONF_HUB` | `Server.SOMFY` |
| `CONF_API_TYPE` | `APIType.CLOUD` |
| `CONF_USERNAME` | account email (pre-fills the reauth form; not a secret) |
| `CONF_REFRESH_TOKEN` | site-scoped rotating refresh token |
| `CONF_SITE_OID` | selected site OID |
| `CONF_REGION` | resolved region (`EMEA`/`APAC`/`SNABA`) |
| `CONF_GATEWAY_ID` | selected gateway id |

- `unique_id` = gateway id (consistent with the cloud and Rexel paths).
- Entry `title` = site label (falls back to gateway id).

New constants in `const.py`: `CONF_REFRESH_TOKEN`, `CONF_SITE_OID`,
`CONF_REGION`. `CONF_GATEWAY_ID` already exists (Rexel).

## Config flow (`config_flow.py`)

### Routing

`async_step_user`: when the picked hub is `Server.SOMFY`, route to a new
`async_step_somfy`. All existing routing (Rexel → OAuth, local-capable →
`local_or_cloud`, else → `cloud`) is unchanged.

### `async_step_somfy` (username/password)

1. Show a username/password form (reuse `CONF_USERNAME`/`CONF_PASSWORD` and the
   common `cloud`-style strings).
2. Build an `OverkizClient(server=Server.SOMFY,
   credentials=UsernamePasswordCredentials(...))`, `await client.login()`, then
   `gateways = await client.discover_gateways()`.
3. Error handling mirrors `async_step_cloud`: `TooManyRequestsError`,
   `BadCredentialsError`/`NotAuthenticatedError` → `invalid_auth`,
   `(TimeoutError, ClientError)` → `cannot_connect`, `MaintenanceError`,
   `TooManyAttemptsBannedError`, and the catch-all `unknown`. (Somfy-specific
   exceptions from the library, e.g. `SomfyBadCredentialsError`, subclass the
   existing bad-credentials / service errors and map to the same buckets.)
4. If `not gateways`: abort `no_gateways` (existing key).
5. If exactly one gateway: `select_gateway`, snapshot, create entry.
6. If more than one: stash the client + candidates and route to the shared
   gateway-selection step.

### Shared gateway-selection step

Generalize the existing `async_step_select_gateway` so it serves both Rexel and
Somfy. Both cases hold a `list[GatewayCandidate]` and differ only in the
per-server "create entry" tail. Approach: keep one `select_gateway` form step
that presents `{gateway_id: label or gateway_id}`; on submit, dispatch to the
correct entry-builder based on which server the flow is handling
(`self._server`). The Rexel-specific `_async_create_rexel_entry` stays; add a
sibling `_async_create_somfy_entry`.

### `_async_create_somfy_entry`

1. `client.select_gateway(gateway_id)` (skipped when already auto-selected for a
   single-site account).
2. `credentials = client.to_credentials()` → read `refresh_token`, `site_oid`,
   `region`, `gateway_id`.
3. `await self.async_set_unique_id(gateway_id, raise_on_progress=False)`.
4. Build entry `data`: `CONF_HUB`, `CONF_API_TYPE=APIType.CLOUD`,
   `CONF_REFRESH_TOKEN`, `CONF_SITE_OID`, `CONF_REGION`, `CONF_GATEWAY_ID`.
5. Reauth: `_abort_if_unique_id_mismatch(reason="reauth_wrong_account")` then
   `async_update_reload_and_abort`. New entry:
   `_abort_if_unique_id_configured()` then `async_create_entry(title=label)`.

### Reauth

`async_step_reauth` already stores `self._server = entry_data[CONF_HUB]`. When
that server is `Server.SOMFY`, route reauth to `async_step_somfy` (username/
password re-entry). The site-match guard in `_async_create_somfy_entry`
(`_abort_if_unique_id_mismatch`) enforces re-authenticating the same gateway.

## Runtime setup (`__init__.py`)

### Client construction

Add `create_somfy_client(hass, entry)`:

```python
async def create_somfy_client(hass, entry):
    async def on_token_refresh(refresh_token: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_REFRESH_TOKEN: refresh_token},
        )

    return OverkizClient(
        server=Server.SOMFY,
        credentials=SomfyTokenCredentials(
            refresh_token=entry.data[CONF_REFRESH_TOKEN],
            site_oid=entry.data[CONF_SITE_OID],
            region=entry.data[CONF_REGION],
            gateway_id=entry.data[CONF_GATEWAY_ID],
            on_token_refresh=on_token_refresh,
        ),
        session=async_create_clientsession(hass),
        settings=OverkizClientSettings(
            action_queue=ActionQueueSettings(), default_rts_command_duration=0
        ),
    )
```

The `on_token_refresh` callback is **required for correctness**: the refresh
token rotates on use, and without persisting the rotated value a later reload
would fail once the stored token is retired.

### Dispatch in `async_setup_entry`

Add a branch **before** the generic cloud branch:

```python
elif entry.data.get(CONF_HUB) == Server.SOMFY:
    client = await create_somfy_client(hass, entry)
```

`api_type` stays `APIType.CLOUD`, so the existing cloud behavior (fetch
`get_action_groups()` scenarios, standard update interval) applies unchanged.
The existing `ConfigEntryAuthFailed` mapping already covers
`BadCredentialsError`/`NotAuthenticatedError`, so an expired/revoked refresh
token triggers reauth without new code.

## Manifest

Point `requirements` at the branch for testing in this feature branch, e.g.
`pyoverkiz[nexity] @ git+https://github.com/iMicknl/python-overkiz-api@feat/somfy-multi-account`.
Before merge this reverts to a normal released `pyoverkiz` version bump.

## strings.json

- New `somfy` step under `config.step` with `username`/`password` data +
  data_description (reuse the `cloud` step's common-key references).
- Reuse existing `no_gateways`, `reauth_wrong_account`, `select_gateway`,
  `invalid_auth`, `cannot_connect`, etc.
- Regenerate `translations/en.json` via
  `python3 -m script.translations develop --integration overkiz` before running
  tests.

## Testing

Extend existing test modules, reusing the shared mock-client fixtures.

`test_config_flow.py`:
- Single-site account: user step → somfy step → auto-select → entry created;
  assert stored data (token bundle, unique_id, title).
- Multi-site account: user step → somfy step → `select_gateway` form →
  selected entry created.
- Auth errors map correctly (`invalid_auth`, `cannot_connect`, `no_gateways`).
- Reauth: same account/gateway succeeds and updates the stored token bundle;
  different gateway aborts `reauth_wrong_account`.

`test_init.py`:
- Setup via token bundle constructs the client and completes setup.
- `on_token_refresh` writes the rotated refresh token back to the entry
  (assert `async_update_entry` receives the new token).
- Expired/revoked token → `ConfigEntryAuthFailed` starts reauth.

Parametrize where practical; use `pytest.param(..., id=...)` for named cases and
snapshot (`.ambr`) assertions where they fit the existing patterns.

## Out of scope

- Migrating existing region-specific Somfy entries
  (`SOMFY_EUROPE`/`AMERICA`/`OCEANIA`) to `Server.SOMFY`. Those keep working
  as-is; `Server.SOMFY` is an additional option.
- Local API for `Server.SOMFY` (cloud-only by design).
