# Home Assistant Sandbox

Sandbox runs selected config-entry integrations in worker processes. The main Home Assistant instance owns configuration, persistence, registries, and proxy entities. Each worker runs a private Home Assistant instance and the integration code.

This is an experimental execution model for trusted code. **It does not provide a security boundary.** The host and worker must use the same Core revision. This package requires the Core changes on the `sandbox` branch.

## Architecture

```mermaid
flowchart LR
    subgraph Host[Main Home Assistant]
        Router[Config-entry and flow router]
        Manager[Worker manager]
        Bridge[Host bridge]
        State[Registries and storage]
        Proxies[Proxy entities]
    end
    subgraph Worker[Worker process]
        Runtime[Private Home Assistant]
        Runners[Entry and flow runners]
        Integrations[Integration code]
        Mirror[Entity, service, and event bridges]
    end
    Router --> Bridge
    Manager --> Runtime
    Bridge <-->|Protobuf over stdio or Unix socket| Runners
    Runners --> Integrations
    Integrations --> Mirror
    Mirror --> Bridge
    Bridge --> State
    Bridge --> Proxies
```

Each worker runs its own Home Assistant instance.

1. Home Assistant includes a router that decides during integration setup whether an integration runs on the host or in a specific worker.
2. The worker manager starts the worker with `python -m homeassistant_sandbox`. The worker starts its Home Assistant instance, then signals readiness.
3. When a user adds a sandboxed integration, its config flow runs inside the worker. The host displays the forms and forwards user input to the worker. When the flow completes, the host creates and persists the config entry.
4. The host sends a config-entry snapshot with canonical entry and subentry IDs. The worker sets it up after startup.
5. The worker sends entity descriptions and state updates. The host registers proxy entities. Each proxy entity represents an entity in a worker. On the host, the sandbox integration provides the proxy entities, but Home Assistant presents them as belonging to the integration and config entry running in the worker. Actions called on the proxy entity are forwarded to and executed by the worker entity. The host retains canonical entity and device identities.
6. Inside the worker, operations on a `Store` from `helpers/storage.py` and updates to config entry data are routed to the host for persistence.

On a worker crash, its proxy entities become unavailable.

## Code map

Paths below are relative to this package.

| Area | Start here |
| --- | --- |
| Host routing and worker management | [router.py](../../homeassistant/components/sandbox/router.py), [manager.py](../../homeassistant/components/sandbox/manager.py) |
| Host ownership checks and entity registration | [bridge.py](../../homeassistant/components/sandbox/bridge.py) |
| Typed proxy entities | [entity/](../../homeassistant/components/sandbox/entity/) |
| Worker startup and shutdown | [runtime.py](homeassistant_sandbox/runtime.py) |
| Integration and flow execution | [entry_runner.py](homeassistant_sandbox/entry_runner.py), [flow_runner.py](homeassistant_sandbox/flow_runner.py) |
| Entity export and configuration writeback | [entity_bridge.py](homeassistant_sandbox/entity_bridge.py), [entry_sync.py](homeassistant_sandbox/entry_sync.py) |
| Wire contract | [sandbox.proto](proto/sandbox.proto), [channel.py](homeassistant_sandbox/channel.py) |
| Host and real-worker tests | [tests/components/sandbox/](../../tests/components/sandbox/) |
| Worker tests and compatibility adapters | [tests/](tests/), [testing/](homeassistant_sandbox/testing/) |

Core hooks live in `config_entries.py`, `bootstrap.py`, and `setup.py` for routing; `helpers/entity_component.py` for proxy entity platforms; `helpers/storage.py` and `helpers/sandbox_context.py` for persistence; and `loader.py` and `helpers/translation.py` for remote metadata and strings. These paths are under `homeassistant/` at the repository root.

## Run locally

Use a separate development configuration. Moving existing entities back to local execution is not implemented.

From the Core repository root:

```sh
uv venv .venv
. .venv/bin/activate
script/setup
deactivate
```

`script/setup` installs integration requirements for Core development. The host starts workers with its own Python interpreter. The worker disables automatic requirement installation, so that environment must contain the selected integration's dependencies.

Start with the `random` integration, which needs no external device or service. Add it to the development configuration:

```yaml
sandbox:
  integrations:
    - random
```

Start the host from the repository root:

```sh
uv run --no-sync hass -c config
```

In Home Assistant, go to **Settings → Devices & services → Helpers**, select **Create helper**, and choose **Random**. Create a sensor or binary sensor. Its config flow and entity run in the worker. The host launches the worker when needed. Running the worker module alone does not connect it to a host.

Selection is not a compatibility allowlist. A missing or empty list leaves routing inactive. For selected domains, the host skips both `async_setup` and synchronous `setup`, even when YAML is present. Only config entries run in the worker. YAML-created instances are outside scope. Startup or setup failure leaves the entry in error, without local fallback.

Built-in code comes from the matching checkout. Custom code requires a registered source resolver with a repository URL, commit ref, and integration path. The worker fetches the source before setup. Marketplace installation metadata is not yet connected to this resolver.

## Tests and protocol changes

Run host tests from the repository root:

```sh
uv run --no-sync pytest tests/components/sandbox
```

Run worker tests in their own environment:

```sh
cd packages/home-assistant-sandbox
uv sync
uv run --no-sync pytest
```

The host suite includes actual subprocess tests. In-process adapters alone do not verify the process boundary. For Core hook changes, also run the affected config-entry, setup, bootstrap, loader, or helper tests.

The protocol is symmetric: either side can send requests, responses, and pushes. Stream frames contain length-prefixed Protobuf messages. Handlers can call back through the channel. Keep the reader free to dispatch replies.

`channel.py`, `codec_protobuf.py`, `messages.py`, `entry_sync.py`, and the generated bindings are mirrored between the host and worker. Change both copies together. After protocol changes, run these commands from the repository root:

```sh
bash packages/home-assistant-sandbox/proto/generate.sh
bash packages/home-assistant-sandbox/proto/check_mirror_drift.sh
bash packages/home-assistant-sandbox/proto/check_drift.sh
uv run --no-sync prek run --files <changed-files>
```

The generator uses a temporary environment with pinned compiler dependencies. Do not edit generated bindings by hand. Add coverage for both ends of a new message, including failure and cleanup behavior.

## Current limits

- Shared Python managers are outside v1. Integrations that need live MQTT, Bluetooth, mesh, or other manager objects from the host need further work. An integration's own client library or coordinator can run in its worker.
- State or registry access across groups is incomplete. Integrations that depend on other integrations need individual verification.
- Streaming, voice, camera, and subscription APIs need additional protocol support. A typed proxy entity does not establish full platform compatibility.
- General options flows, worker-initiated reauth, progress/external flow steps, and registry rename/disable parity remain incomplete. Initial entry setup failures require manual reload.
- Stdio and Unix sockets are implemented. Remote WebSocket transport and importing entities from an independent Home Assistant are proposals, not implemented features.
- Container deployment is outside v1.

## Work together

Use merges to bring `dev` into the shared `sandbox` branch. Do not rebase or force-push the shared branch. Build focused changes on top of it so other contributors can follow the history.

Keep changes within one area where possible: host routing, worker lifecycle, proxy entities, protocol, or tests. For changes across areas, include both sides in the same commit. Preserve ownership checks, entry/subentry IDs, and cleanup on unload or disconnect.

Keep this README aligned with the implementation. Document limitations when adding partial support. Detailed contributor guides can move to [Home Assistant Contributors](https://contributors.home-assistant.io/) when the interfaces are ready.
