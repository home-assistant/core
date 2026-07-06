# Overkiz Somfy multi-account Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a region-agnostic `Server.SOMFY` cloud path to the Overkiz integration that supports Somfy multi-site accounts, storing a resumable site-scoped token.

**Architecture:** The config flow gains a `somfy` username/password step that logs in, discovers all sites via `discover_gateways()`, and (auto-)selects one — reusing the existing Rexel `select_gateway` step. On selection it snapshots `client.to_credentials()` and stores the token bundle. At runtime `create_somfy_client` rebuilds the client from `SomfyTokenCredentials`, with an `on_token_refresh` callback persisting the rotating refresh token back to the entry.

**Tech Stack:** Python 3.14, Home Assistant config-flow framework, `python-overkiz-api` (`feat/somfy-multi-account` branch), pytest.

## Global Constraints

- Home Assistant minimum Python version is 3.14. Do not add `from __future__ import annotations` for forward references; annotations are lazy (PEP 649).
- All commands run through the devcontainer CLI with an absolute `--workspace-folder`, never on the host.
- Run `uv run pytest` for tests. Do not amend/squash/force-push after a commit is pushed; make new commits.
- After editing `strings.json`, regenerate translations: `python3 -m script.translations develop --integration overkiz` before running tests.
- Test function parameters must have type annotations; prefer concrete types (`HomeAssistant`, `MockConfigEntry`). Prefer `@pytest.mark.usefixtures` when an argument is unused.
- `Server.SOMFY` is cloud-only (not in `SERVERS_WITH_LOCAL_API`) and already present in the library `SUPPORTED_SERVERS`, so it appears in the server picker automatically.
- Config entry stores **token only** — no username/password on disk.
- Devcontainer test command form:
  `devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run pytest <args>`
- **The `pyoverkiz` `feat/somfy-multi-account` branch design is NOT final.** As you implement, record every point of friction, awkward API surface, bug, or improvement idea in `docs/superpowers/notes/pyoverkiz-somfy-multi-account-feedback.md` (create it in Task 1). This file feeds back into the library PR; it is not part of the HA change and is never committed to the integration.

---

## Task 1: Bump manifest to the feature branch

**Files:**
- Modify: `homeassistant/components/overkiz/manifest.json`
- Modify: `requirements_all.txt`, `requirements_test_all.txt` (generated)

**Interfaces:**
- Produces: `SomfyTokenCredentials`, `Server.SOMFY`, `client.discover_gateways()`, `client.select_gateway()`, `client.to_credentials()` become importable from the installed `pyoverkiz`.

- [ ] **Step 0: Create the pyoverkiz feedback notes file**

Create `docs/superpowers/notes/pyoverkiz-somfy-multi-account-feedback.md` with this skeleton. Append to it throughout every later task whenever the library API is awkward, buggy, under-documented, or could be improved. Record: what you were doing, what the library did, and what would have been better. Do NOT commit this file — it is out-of-tree feedback for the library PR.

```markdown
# pyoverkiz `feat/somfy-multi-account` — integration feedback

_Findings while wiring the branch into Home Assistant. Design is not final._

## API friction / awkwardness

- (none yet)

## Bugs / unexpected behavior

- (none yet)

## Docs / typing gaps

- (none yet)

## Improvement ideas

- (none yet)
```

- [ ] **Step 1: Point the requirement at the branch**

In `homeassistant/components/overkiz/manifest.json`, change the `requirements` entry from:

```json
"requirements": ["pyoverkiz[nexity]==2.0.3"],
```

to:

```json
"requirements": ["pyoverkiz[nexity] @ git+https://github.com/iMicknl/python-overkiz-api@feat/somfy-multi-account"],
```

- [ ] **Step 2: Regenerate requirements and install**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run python -m script.gen_requirements_all
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv pip install -e .
```
Expected: `requirements_all.txt` / `requirements_test_all.txt` updated with the git URL; install succeeds.

- [ ] **Step 3: Verify the new API is importable**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run python -c "from pyoverkiz.auth.credentials import SomfyTokenCredentials; from pyoverkiz.enums import Server; print(Server.SOMFY, SomfyTokenCredentials)"
```
Expected: prints `Server.SOMFY somfy <class '...SomfyTokenCredentials'>` with no ImportError.

- [ ] **Step 4: Commit**

```bash
git add homeassistant/components/overkiz/manifest.json requirements_all.txt requirements_test_all.txt
git commit -m "chore(overkiz): pin pyoverkiz to somfy-multi-account branch for testing"
```

---

## Task 2: Add config constants

**Files:**
- Modify: `homeassistant/components/overkiz/const.py:37-39`

**Interfaces:**
- Produces: `CONF_REFRESH_TOKEN = "refresh_token"`, `CONF_SITE_OID = "site_oid"`, `CONF_REGION = "region"` (module-level `Final` constants). `CONF_GATEWAY_ID` already exists.

- [ ] **Step 1: Add the constants**

In `homeassistant/components/overkiz/const.py`, after the existing `CONF_GATEWAY_ID` line (currently line 39), add:

```python
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_SITE_OID: Final = "site_oid"
CONF_REGION: Final = "region"
```

- [ ] **Step 2: Verify it imports**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run python -c "from homeassistant.components.overkiz.const import CONF_REFRESH_TOKEN, CONF_SITE_OID, CONF_REGION; print(CONF_REFRESH_TOKEN, CONF_SITE_OID, CONF_REGION)"
```
Expected: prints `refresh_token site_oid region`.

- [ ] **Step 3: Commit**

```bash
git add homeassistant/components/overkiz/const.py
git commit -m "feat(overkiz): add Somfy multi-account config constants"
```

---

## Task 3: Config flow — single-site Somfy flow (TDD)

**Files:**
- Modify: `homeassistant/components/overkiz/config_flow.py`
- Test: `tests/components/overkiz/test_config_flow.py`

**Interfaces:**
- Consumes: `CONF_REFRESH_TOKEN`, `CONF_SITE_OID`, `CONF_REGION` (Task 2); `Server.SOMFY`, `SomfyTokenCredentials`, `SomfyServiceError`, `GatewayCandidate`, `client.discover_gateways()`, `client.select_gateway()`, `client.to_credentials()`.
- Produces: `async_step_somfy`, `_async_create_somfy_entry`. A `to_credentials()` return object exposes attributes `refresh_token: str`, `site_oid: str`, `region: str`, `gateway_id: str | None`.

- [ ] **Step 1: Write the failing test for the single-site flow**

Add to `tests/components/overkiz/test_config_flow.py`. First add a shared constant near the other `TEST_*` constants (top of file):

```python
TEST_REFRESH_TOKEN = "somfy-refresh-token"
TEST_SITE_OID = "site-oid-1"
TEST_REGION = "EMEA"
```

Add this import at the top with the other pyoverkiz imports:

```python
from pyoverkiz.auth.credentials import SomfyTokenCredentials
```

Add the test:

```python
async def test_somfy_full_flow_single_site(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """A single-site Somfy account auto-selects and stores a token bundle."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "somfy"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "somfy"

    credentials = SomfyTokenCredentials(
        refresh_token=TEST_REFRESH_TOKEN,
        site_oid=TEST_SITE_OID,
        region=TEST_REGION,
        gateway_id=TEST_GATEWAY_ID,
    )

    with (
        patch("pyoverkiz.client.OverkizClient.login", return_value=True),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
            return_value=[
                GatewayCandidate(gateway_id=TEST_GATEWAY_ID, label="My Home")
            ],
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.select_gateway"
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.to_credentials",
            return_value=credentials,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Home"
    assert result["result"].unique_id == TEST_GATEWAY_ID
    assert result["data"]["hub"] == "somfy"
    assert result["data"]["api_type"] == "cloud"
    assert result["data"]["refresh_token"] == TEST_REFRESH_TOKEN
    assert result["data"]["site_oid"] == TEST_SITE_OID
    assert result["data"]["region"] == TEST_REGION
    assert result["data"]["gateway_id"] == TEST_GATEWAY_ID
    assert "password" not in result["data"]
    assert len(mock_setup_entry.mock_calls) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run pytest tests/components/overkiz/test_config_flow.py::test_somfy_full_flow_single_site -v
```
Expected: FAIL — the `somfy` step does not exist, so the flow does not reach the `somfy` form (KeyError/UnknownStep or wrong step_id).

- [ ] **Step 3: Route the user step to `async_step_somfy`**

In `config_flow.py` `async_step_user`, add a branch after the Rexel branch (after the `if self._server == Server.REXEL:` block, before `return await self.async_step_cloud()`):

```python
            # Somfy multi-account uses username/password login plus site discovery.
            if self._server == Server.SOMFY:
                return await self.async_step_somfy()
```

- [ ] **Step 4: Add imports**

At the top of `config_flow.py`, extend the credentials import and the const import:

```python
from pyoverkiz.auth.credentials import (
    LocalTokenCredentials,
    RexelTokenCredentials,
    SomfyTokenCredentials,
    UsernamePasswordCredentials,
)
```

Add `SomfyServiceError` to the `pyoverkiz.exceptions` import block.

Extend the `.const` import to include `CONF_REFRESH_TOKEN`, `CONF_REGION`, `CONF_SITE_OID` (alongside the existing `CONF_API_TYPE`, `CONF_GATEWAY_ID`, `CONF_HUB`, ...).

- [ ] **Step 5: Implement `async_step_somfy` and `_async_create_somfy_entry`**

Add these methods to `OverkizConfigFlow` (place near the Rexel gateway methods):

```python
    async def async_step_somfy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Somfy multi-account username/password login and site discovery."""
        errors: dict[str, str] = {}

        if user_input:
            self._user = user_input[CONF_USERNAME]
            session = async_create_clientsession(self.hass)
            self._somfy_client = OverkizClient(
                server=Server.SOMFY,
                credentials=UsernamePasswordCredentials(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                ),
                session=session,
            )

            try:
                await self._somfy_client.login(register_event_listener=False)
                self._somfy_gateways = await self._somfy_client.discover_gateways()
            except TooManyRequestsError:
                errors["base"] = "too_many_requests"
            except (BadCredentialsError, NotAuthenticatedError):
                errors["base"] = "invalid_auth"
            except (TimeoutError, ClientError, SomfyServiceError):
                errors["base"] = "cannot_connect"
            except MaintenanceError:
                errors["base"] = "server_in_maintenance"
            except TooManyAttemptsBannedError:
                errors["base"] = "too_many_attempts"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
                LOGGER.exception("Unknown error")
            else:
                if not self._somfy_gateways:
                    return self.async_abort(reason="no_gateways")

                if len(self._somfy_gateways) == 1:
                    return await self._async_create_somfy_entry(
                        self._somfy_gateways[0]
                    )

                return await self.async_step_select_gateway()

        return self.async_show_form(
            step_id="somfy",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=self._user): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def _async_create_somfy_entry(
        self, gateway: GatewayCandidate
    ) -> ConfigFlowResult:
        """Scope the client to the chosen site and persist its token bundle."""
        self._somfy_client.select_gateway(gateway.gateway_id)
        credentials = self._somfy_client.to_credentials()

        await self.async_set_unique_id(
            gateway.gateway_id, raise_on_progress=False
        )

        data = {
            CONF_HUB: Server.SOMFY,
            CONF_API_TYPE: APIType.CLOUD,
            CONF_REFRESH_TOKEN: credentials.refresh_token,
            CONF_SITE_OID: credentials.site_oid,
            CONF_REGION: credentials.region,
            CONF_GATEWAY_ID: gateway.gateway_id,
        }

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="reauth_wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=gateway.label or gateway.gateway_id, data=data
        )
```

Add the class-level attribute declarations near the existing `_rexel_gateways` declaration:

```python
    _somfy_client: OverkizClient
    _somfy_gateways: list[GatewayCandidate]
```

Also import `APIType` in `config_flow.py` if not already imported from `pyoverkiz.enums` (it is: line 15). Ensure `TooManyRequestsError`, `NotAuthenticatedError`, `BadCredentialsError`, `MaintenanceError`, `TooManyAttemptsBannedError` are imported (all already present).

- [ ] **Step 6: Run test to verify it passes**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run pytest tests/components/overkiz/test_config_flow.py::test_somfy_full_flow_single_site -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add homeassistant/components/overkiz/config_flow.py tests/components/overkiz/test_config_flow.py
git commit -m "feat(overkiz): add Somfy multi-account config flow (single site)"
```

---

## Task 4: Config flow — multi-site selection reuses `select_gateway` (TDD)

**Files:**
- Modify: `homeassistant/components/overkiz/config_flow.py` (`async_step_select_gateway`)
- Test: `tests/components/overkiz/test_config_flow.py`

**Interfaces:**
- Consumes: `async_step_somfy`, `_async_create_somfy_entry` (Task 3); existing `async_step_select_gateway`, `_async_create_rexel_entry`, `self._rexel_gateways`, `self._somfy_gateways`, `self._server`.
- Produces: a generalized `async_step_select_gateway` that dispatches by `self._server`.

- [ ] **Step 1: Write the failing test for the multi-site flow**

Add to `tests/components/overkiz/test_config_flow.py`:

```python
async def test_somfy_full_flow_multiple_sites(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """A multi-site Somfy account shows the gateway selection step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "somfy"}
    )

    assert result["step_id"] == "somfy"

    credentials = SomfyTokenCredentials(
        refresh_token=TEST_REFRESH_TOKEN,
        site_oid=TEST_SITE_OID,
        region=TEST_REGION,
        gateway_id=TEST_GATEWAY_ID2,
    )

    with (
        patch("pyoverkiz.client.OverkizClient.login", return_value=True),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
            return_value=[
                GatewayCandidate(gateway_id=TEST_GATEWAY_ID, label="Home"),
                GatewayCandidate(gateway_id=TEST_GATEWAY_ID2, label="Cabin"),
            ],
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.select_gateway"
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.to_credentials",
            return_value=credentials,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_gateway"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"gateway_id": TEST_GATEWAY_ID2}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cabin"
    assert result["result"].unique_id == TEST_GATEWAY_ID2
    assert result["data"]["gateway_id"] == TEST_GATEWAY_ID2
    assert result["data"]["site_oid"] == TEST_SITE_OID
    assert len(mock_setup_entry.mock_calls) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run pytest tests/components/overkiz/test_config_flow.py::test_somfy_full_flow_multiple_sites -v
```
Expected: FAIL — `async_step_select_gateway` only knows the Rexel gateway list and Rexel entry builder, so it raises `StopIteration`/`AttributeError` or builds a Rexel entry.

- [ ] **Step 3: Generalize `async_step_select_gateway`**

Replace the body of `async_step_select_gateway` in `config_flow.py` with a version that dispatches on `self._server`:

```python
    async def async_step_select_gateway(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a gateway on a multi-gateway account."""
        if self._server == Server.SOMFY:
            candidates = self._somfy_gateways
        else:
            candidates = self._rexel_gateways

        if user_input:
            gateway = next(
                candidate
                for candidate in candidates
                if candidate.gateway_id == user_input[CONF_GATEWAY_ID]
            )
            if self._server == Server.SOMFY:
                return await self._async_create_somfy_entry(gateway)
            return await self._async_create_rexel_entry(gateway)

        return self.async_show_form(
            step_id="select_gateway",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GATEWAY_ID): vol.In(
                        {
                            candidate.gateway_id: candidate.label
                            or candidate.gateway_id
                            for candidate in candidates
                        }
                    ),
                }
            ),
        )
```

Note: the Rexel `GatewayCandidate.gateway_id` and Somfy `GatewayCandidate.gateway_id` are the same attribute (`gateway_id`), so the comprehension is unchanged.

- [ ] **Step 4: Run both Somfy flow tests to verify they pass**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run pytest tests/components/overkiz/test_config_flow.py -k somfy -v
```
Expected: `test_somfy_full_flow_single_site` and `test_somfy_full_flow_multiple_sites` PASS.

- [ ] **Step 5: Run the Rexel tests to confirm no regression**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run pytest tests/components/overkiz/test_config_flow.py -k rexel -v
```
Expected: all Rexel tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add homeassistant/components/overkiz/config_flow.py tests/components/overkiz/test_config_flow.py
git commit -m "feat(overkiz): reuse select_gateway step for Somfy multi-site"
```

---

## Task 5: Config flow — error handling and reauth (TDD)

**Files:**
- Modify: `homeassistant/components/overkiz/config_flow.py` (`async_step_reauth`)
- Test: `tests/components/overkiz/test_config_flow.py`

**Interfaces:**
- Consumes: `async_step_somfy` (Task 3), existing `async_step_reauth`.
- Produces: reauth routing to `async_step_somfy` when `self._server == Server.SOMFY`.

- [ ] **Step 1: Write failing tests for no_gateways, invalid_auth, and reauth**

Add to `tests/components/overkiz/test_config_flow.py`:

```python
async def test_somfy_flow_no_sites(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """A Somfy account without sites aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "somfy"}
    )

    with (
        patch("pyoverkiz.client.OverkizClient.login", return_value=True),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
            return_value=[],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_gateways"


async def test_somfy_flow_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Invalid Somfy credentials show an error on the somfy step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "somfy"}
    )

    with patch(
        "pyoverkiz.client.OverkizClient.login",
        side_effect=BadCredentialsError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "somfy"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_somfy_reauth_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Somfy reauth re-runs username/password login for the same gateway."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        version=1,
        minor_version=2,
        data={
            "hub": "somfy",
            "api_type": "cloud",
            "refresh_token": "old-token",
            "site_oid": TEST_SITE_OID,
            "region": TEST_REGION,
            "gateway_id": TEST_GATEWAY_ID,
        },
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "somfy"

    credentials = SomfyTokenCredentials(
        refresh_token="new-token",
        site_oid=TEST_SITE_OID,
        region=TEST_REGION,
        gateway_id=TEST_GATEWAY_ID,
    )

    with (
        patch("pyoverkiz.client.OverkizClient.login", return_value=True),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
            return_value=[
                GatewayCandidate(gateway_id=TEST_GATEWAY_ID, label="My Home")
            ],
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.select_gateway"
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.to_credentials",
            return_value=credentials,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data["refresh_token"] == "new-token"


async def test_somfy_reauth_wrong_account(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Somfy reauth with a different gateway aborts."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        version=1,
        minor_version=2,
        data={
            "hub": "somfy",
            "api_type": "cloud",
            "refresh_token": "old-token",
            "site_oid": TEST_SITE_OID,
            "region": TEST_REGION,
            "gateway_id": TEST_GATEWAY_ID,
        },
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)
    assert result["step_id"] == "somfy"

    credentials = SomfyTokenCredentials(
        refresh_token="new-token",
        site_oid="other-site",
        region=TEST_REGION,
        gateway_id=TEST_GATEWAY_ID2,
    )

    with (
        patch("pyoverkiz.client.OverkizClient.login", return_value=True),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
            return_value=[
                GatewayCandidate(gateway_id=TEST_GATEWAY_ID2, label="Other")
            ],
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.select_gateway"
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.to_credentials",
            return_value=credentials,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_wrong_account"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run pytest tests/components/overkiz/test_config_flow.py -k "somfy_flow_no_sites or somfy_flow_invalid_auth or somfy_reauth" -v
```
Expected: `no_sites` and `invalid_auth` PASS already (Task 3 handles them); both reauth tests FAIL — reauth currently routes Somfy to `async_step_user` → but `async_step_user` was passed `entry_data` and re-shows the picker rather than the somfy step.

(If `no_sites`/`invalid_auth` already pass, that is fine — they lock in behavior. Focus the fix on reauth.)

- [ ] **Step 3: Route reauth to the somfy step**

In `async_step_reauth` in `config_flow.py`, the method currently ends with `return await self.async_step_user(dict(entry_data))`. Add a Somfy branch before that return, after the `elif self._server != Server.REXEL:` block:

```python
        if self._server == Server.SOMFY:
            return await self.async_step_somfy()
```

Verify the full tail of `async_step_reauth` reads:

```python
        self._api_type = entry_data.get(CONF_API_TYPE, APIType.CLOUD)
        self._server = entry_data[CONF_HUB]

        if self._api_type == APIType.LOCAL:
            self._host = entry_data[CONF_HOST]
            self._verify_ssl = entry_data[CONF_VERIFY_SSL]
        # Rexel cloud reauth re-runs the OAuth2 flow; there is no stored username.
        elif self._server != Server.REXEL:
            self._user = entry_data[CONF_USERNAME]

        if self._server == Server.SOMFY:
            return await self.async_step_somfy()

        return await self.async_step_user(dict(entry_data))
```

Because Somfy no longer stores `CONF_USERNAME`, the `elif self._server != Server.REXEL:` branch would raise `KeyError` for Somfy entries. Change that guard to also exclude Somfy:

```python
        # Rexel and Somfy cloud reauth re-run their own login; no stored username.
        elif self._server not in {Server.REXEL, Server.SOMFY}:
            self._user = entry_data[CONF_USERNAME]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run pytest tests/components/overkiz/test_config_flow.py -k somfy -v
```
Expected: all Somfy tests PASS.

- [ ] **Step 5: Commit**

```bash
git add homeassistant/components/overkiz/config_flow.py tests/components/overkiz/test_config_flow.py
git commit -m "feat(overkiz): handle Somfy multi-account reauth and errors"
```

---

## Task 6: Runtime client setup + token persistence (TDD)

**Files:**
- Modify: `homeassistant/components/overkiz/__init__.py`
- Test: `tests/components/overkiz/test_init.py`, `tests/components/overkiz/conftest.py`

**Interfaces:**
- Consumes: `CONF_REFRESH_TOKEN`, `CONF_SITE_OID`, `CONF_REGION`, `CONF_GATEWAY_ID`, `SomfyTokenCredentials`, `Server.SOMFY`.
- Produces: `create_somfy_client(hass, entry) -> OverkizClient` (async). Dispatch in `async_setup_entry` selects it when `entry.data.get(CONF_HUB) == Server.SOMFY`.

- [ ] **Step 1: Add a Somfy entry fixture**

In `tests/components/overkiz/conftest.py`, after `mock_rexel_config_entry`, add:

```python
@pytest.fixture
def mock_somfy_config_entry() -> MockConfigEntry:
    """Return a Somfy multi-account config entry backed by a token bundle."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={
            "hub": "somfy",
            "api_type": "cloud",
            "refresh_token": "somfy-refresh-token",
            "site_oid": "site-oid-1",
            "region": "EMEA",
            "gateway_id": TEST_GATEWAY_ID,
        },
    )
```

- [ ] **Step 2: Write the failing test for token persistence**

Add to `tests/components/overkiz/test_init.py` (mirror the existing import style; import `patch`, `MockOverkizClient`, `MockConfigEntry` as already used there):

```python
async def test_somfy_setup_persists_rotated_token(
    hass: HomeAssistant,
    mock_somfy_config_entry: MockConfigEntry,
    mock_client: MockOverkizClient,
) -> None:
    """create_somfy_client wires on_token_refresh to persist the rotated token."""
    mock_somfy_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.overkiz.create_somfy_client",
        return_value=mock_client,
    ) as create_client:
        await hass.config_entries.async_setup(mock_somfy_config_entry.entry_id)
        await hass.async_block_till_done()

    assert create_client.call_count == 1
    assert mock_somfy_config_entry.state is ConfigEntryState.LOADED
```

Add a second test that exercises the real `create_somfy_client` callback:

```python
async def test_somfy_on_token_refresh_updates_entry(
    hass: HomeAssistant,
    mock_somfy_config_entry: MockConfigEntry,
) -> None:
    """The on_token_refresh callback writes the new refresh token to the entry."""
    from homeassistant.components.overkiz import create_somfy_client

    mock_somfy_config_entry.add_to_hass(hass)

    client = await create_somfy_client(hass, mock_somfy_config_entry)
    callback = client._auth.credentials.on_token_refresh
    await callback("rotated-token")

    assert mock_somfy_config_entry.data["refresh_token"] == "rotated-token"
    assert mock_somfy_config_entry.data["site_oid"] == "site-oid-1"
```

Ensure `ConfigEntryState` is imported in `test_init.py` (add `from homeassistant.config_entries import ConfigEntryState` if absent).

- [ ] **Step 3: Run tests to verify they fail**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run pytest tests/components/overkiz/test_init.py -k somfy -v
```
Expected: FAIL — `create_somfy_client` does not exist (ImportError / AttributeError).

- [ ] **Step 4: Implement `create_somfy_client` and dispatch**

In `homeassistant/components/overkiz/__init__.py`:

Add to the credentials import:

```python
from pyoverkiz.auth.credentials import (
    LocalTokenCredentials,
    RexelTokenCredentials,
    SomfyTokenCredentials,
    UsernamePasswordCredentials,
)
```

Add to the `.const` import: `CONF_REFRESH_TOKEN`, `CONF_REGION`, `CONF_SITE_OID`.

Add the dispatch branch in `async_setup_entry`, before the final `else` cloud branch:

```python
    # Somfy multi-account Cloud API (resumable token)
    elif entry.data.get(CONF_HUB) == Server.SOMFY:
        client = await create_somfy_client(hass, entry)
```

Add the factory near `create_rexel_client`:

```python
async def create_somfy_client(
    hass: HomeAssistant, entry: OverkizDataConfigEntry
) -> OverkizClient:
    """Create an Overkiz client for a Somfy multi-account, resumed from a token."""

    async def on_token_refresh(refresh_token: str) -> None:
        """Persist the rotated Somfy refresh token back to the config entry."""
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

- [ ] **Step 5: Run tests to verify they pass**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run pytest tests/components/overkiz/test_init.py -k somfy -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add homeassistant/components/overkiz/__init__.py tests/components/overkiz/test_init.py tests/components/overkiz/conftest.py
git commit -m "feat(overkiz): set up Somfy multi-account client with token persistence"
```

---

## Task 7: Strings and translations

**Files:**
- Modify: `homeassistant/components/overkiz/strings.json`
- Generated: `homeassistant/components/overkiz/translations/en.json`

**Interfaces:**
- Consumes: the `somfy` `step_id` and error keys used by Task 3/5 (`invalid_auth`, `cannot_connect`, `no_gateways`, `too_many_requests`, `server_in_maintenance`, `too_many_attempts`, `unknown` — all already present).

- [ ] **Step 1: Add the `somfy` step to strings.json**

In `homeassistant/components/overkiz/strings.json`, under `config.step`, add a `somfy` entry (keep keys alphabetically ordered — place after `select_gateway`, before `user`):

```json
      "somfy": {
        "data": {
          "password": "[%key:common::config_flow::data::password%]",
          "username": "[%key:common::config_flow::data::username%]"
        },
        "data_description": {
          "password": "The password of your Somfy account (app).",
          "username": "The username of your Somfy account (app)."
        },
        "description": "Enter your Somfy account credentials. All homes on your account will be discovered so you can choose one."
      },
```

- [ ] **Step 2: Regenerate the English translations**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run python -m script.translations develop --integration overkiz
```
Expected: `translations/en.json` updated with the `somfy` step.

- [ ] **Step 3: Verify strings pass hassfest**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run python -m script.hassfest -p overkiz
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add homeassistant/components/overkiz/strings.json homeassistant/components/overkiz/translations/en.json
git commit -m "feat(overkiz): add Somfy multi-account config flow strings"
```

---

## Task 8: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full Overkiz test suite**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run pytest tests/components/overkiz/ -v
```
Expected: all tests PASS.

- [ ] **Step 2: Run lint/format/type checks**

Run:
```
devcontainer exec --workspace-folder /Users/mick/Projects/home-assistant-core uv run prek run --all-files
```
Expected: all hooks pass (ruff, mypy, pylint, hassfest, prettier).

- [ ] **Step 3: Fix any issues and commit**

If any check fails, fix inline and commit with a descriptive message. Do not amend earlier commits.

- [ ] **Step 4: Consolidate pyoverkiz feedback**

Review `docs/superpowers/notes/pyoverkiz-somfy-multi-account-feedback.md`, tidy the accumulated notes into clear, actionable points, and summarize the top findings back to the user so they can feed them into the library PR. Do not commit this file to the integration.

---

## Self-Review Notes

- **Spec coverage:** flow routing (Task 3), token-only storage (Tasks 3/6), config entry data (Task 3), shared select_gateway (Task 4), reauth (Task 5), on_token_refresh persistence (Task 6), manifest (Task 1), strings/translations (Task 7), tests throughout. Migration of legacy Somfy servers is explicitly out of scope per the spec.
- **Type consistency:** `create_somfy_client` (async) referenced identically in Task 6 dispatch and factory; `_async_create_somfy_entry`, `async_step_somfy`, `self._somfy_client`, `self._somfy_gateways` consistent across Tasks 3–5; `to_credentials()` attributes `refresh_token`/`site_oid`/`region`/`gateway_id` match `SomfyTokenCredentials` fields.
- **Note for implementer:** `client._auth.credentials.on_token_refresh` in Task 6 Step 2 reaches into the client internals to fetch the callback for direct testing; if the real client structure differs, assert the write-back by invoking whatever attribute holds the callback, or capture it via patching `SomfyTokenCredentials`.
