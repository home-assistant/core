# IAMMETER asynchronous Core testing preview

This working tree is a local follow-up to `iammeter-config-flow`. It requires the
matching `iammeter==0.3.0` asynchronous library candidate. Neither these local
changes nor this library version have been published. The remote preview
branches may still contain the older 0.2.2 baseline. This is not an official HA
release, and no official Core PR is created by this testing procedure.

## Isolated local setup

Use Linux, Python >=3.14.2 compatible with the checkout, Git, uv, and the normal
Core development build prerequisites. Keep the Core checkout, configuration and
database separate from production. With the candidate library at `../library`:

```bash
uv venv --python 3.14 .venv
source .venv/bin/activate
uv pip install -e . -e packages/pytest-home-assistant -r requirements_test.txt ../library
python3 -m script.translations develop --all
mkdir -p ../iammeter-test-config
SETUP_PORT=8124 python3 -m homeassistant --config ../iammeter-test-config --skip-pip
```

This installs the targeted development dependencies; `script/setup` additionally
installs all integration dependencies. Full dependency setup and official Core
submission require the pinned library to be published to PyPI first. `--skip-pip`
prevents installation attempts for that unpublished candidate; dependencies for
other enabled integrations must be preinstalled at the checkout's versions.

The current Windows Docker lab is at `D:\tmp\iammeter-ha-local-test` and uses
its Start-Test.ps1, Stop-Test.ps1 and Run-Tests.ps1 scripts. Open
http://localhost:8124/config/integrations to compare Core, HACS HTTP and Modbus.
Device addresses, credentials, raw readings and databases are private artifacts.

## Behavior to check

- The integration and manufacturer are named IAMMETER. Add by host/port or a full
  HTTP/HTTPS URL. `/monitorjson` is appended once; a full URL controls its port.
- The independent async client receives HA's session. Core polling remains fully
  asynchronous. The package also retains the original `Client` / `IamMeter`
  synchronous APIs and deprecated `power_meter` module for compatibility; Core
  does not use them. Their requests/voluptuous dependencies are included.
- The seven parsed models are WEM3080, WEM3162, WEM3080T, WEM3046T, WEM3050T,
  WEM3063T and WEM2067. WEM3162 may use a stable MAC when no SN is returned.
  A device without either stable identity is rejected; IP is never its identity.
- Device information includes model, firmware and serial when returned by the
  meter, and a Visit link. All returned measurement fields are enabled by default;
  explicit user disablement and HA's disable-new-entities preference are retained.
- Sensor names identify measurements and phases. New entity IDs derive from
  those names; existing entity IDs remain unchanged to preserve references.
- WEM2067 has A/B, never C. Optional NET and reactive fields are discovered when
  first reported on every multi-channel model. Missing fields become unavailable,
  remain registered, and recover without duplicates. Missing fields are not zero.
- Power factor uses the meter's unitless ratio, such as 0.95. Config entry schema
  1.2 migrates old default percent presentation while preserving explicit user
  unit preferences. HA's ratio converter normalizes new values into historical
  percent statistics; existing statistics are not manually rewritten.
- Adding and reconfiguring use the stable identity. Reconfigure changes the
  address of the same meter. Polling a different identity continues, matching the
  HACS HTTP behavior, but opens a visible Repairs warning about possible mixed
  history. The warning clears when the original meter returns.
- Authentication is anonymous first, with one legacy fallback after a 401.
  Optional custom credentials and reauthentication are supported. Polling uses
  the original 30-second default; no polling-frequency setting is exposed.
- HACS HTTP and Modbus remain independent. Core adds no SSDP matching or HACS
  migration. Avoid counting equivalent energy readings twice in Energy Dashboard.
- Test legacy YAML only with a backup of the original configuration and database.
  Verify entity IDs, long-term statistics and Energy Dashboard references.

## Automated checks

```bash
uv run --active --no-sync pytest -q tests/components/iammeter --cov=homeassistant.components.iammeter --cov-report=term-missing
uv run --active --no-sync ruff check homeassistant/components/iammeter tests/components/iammeter
uv run --active --no-sync python3 -m script.hassfest --integration-path homeassistant/components/iammeter
```

Test logs in the local lab record the exact final counts and static-check results.
The lab checks physical WEM3080, WEM3080T, WEM3046T, WEM3050T and two WEM2067
meters. WEM3162 and WEM3063T coverage is synthetic. The excluded device ending
in 109 is not used. Physical dynamic NET changes and migration of a production
historical database remain separate acceptance gates. Full-repository prek must
be completed before submission; a timed attempt is not a passing result.

## Stop and revert

Stop only the test instance. A complete configuration backup was made before the
upgrade. Roll back both the source and matching library together, and restore the
corresponding configuration backup; do not point old HA at the upgraded preview
database. No PyPI upload, remote Git push, issue or PR is part of this local test.
