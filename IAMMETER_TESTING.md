# IAMMETER colleague testing preview

This branch is an experimental Home Assistant Core checkout, not an official HA release or a HACS package. Use a separate test configuration and database. The matching `iammeter==0.2.2` library is a local candidate and has not been published to PyPI.

## Run from source

Use Python 3.14.2 or newer compatible with this Core checkout, Git, uv and the platform build dependencies described in the repository development documentation.

```bash
git clone --branch iammeter-config-flow https://github.com/lewei50/core.git iammeter-core-test
cd iammeter-core-test
script/setup
source .venv/bin/activate
uv pip install --python .venv/bin/python "git+https://github.com/lewei50/iammeter_pip_lib.git@a804336e87717eeb4960e2c8c37a60d66da681a8"
python3 -m script.translations develop --integration iammeter
mkdir -p ../iammeter-test-config
SETUP_PORT=8124 python3 -m homeassistant --config ../iammeter-test-config --skip-pip
```

`script/setup` installs development dependencies for the full Core checkout and can require compilers and system libraries. The preview library must be installed after dependency setup, which may otherwise install the old library. `--skip-pip` avoids attempting to fetch the unpublished candidate, so other integrations must have their dependencies preinstalled. This preview is intended for developers; copying Core files into an installed HA instance is not the installation procedure.

Open `http://localhost:8124`, complete onboarding, then Settings → Devices & services → Add integration → IamMeter. Replace localhost with the test host address when using another computer. Keep this configuration separate from an existing HA instance.

## Check the behavior

- Add a physical meter by IP/hostname and port, or enter a full HTTP/HTTPS URL. A directory URL such as `https://simulator.iammeter.com/WEM2067/` automatically receives `/monitorjson`; URL protocol/port take precedence over the separate port field.
- Confirm single-phase and three-phase readings. WEM2067 exposes A/B only, 14 entities without NET and 20 with NET. A/B power and energy are enabled by default; all NET readings are disabled by default. Enable optional readings in the entity settings as needed.
- Confirm WEM2067 NET discovery when it first appears. Previously discovered NET readings become unavailable when absent and recover without duplicate entities when restored. No C channel or reactive readings are included.
- Add the same device again and confirm duplicate detection by the response `SN`. Public simulator endpoints may share a test serial; inspect returned SN values before trying several simulator models. Use separate configurations for endpoints that share an SN. Reconfigure accepts only the same SN.
- Disconnect and restore a test meter, reload the integration, restart HA, and confirm readings recover. Record HA version, meter model/firmware, reproducible steps and sanitized logs for any failure.
- Test legacy YAML migration only against a backup copy of the original configuration/database. Compare entity IDs, statistics and Energy Dashboard references. Synthetic tests do not establish real-history migration compatibility.

## Automated validation and limits

```bash
uv pip install --python .venv/bin/python pytest-cov
uv run --no-sync pytest -q tests/components/iammeter --cov=homeassistant.components.iammeter --cov-report=term-missing
```

The preview has 74 passing Core tests with 100% integration line coverage and 61 passing library tests. Targeted Ruff, mypy and hassfest passed. Full-repository prek did not finish within the allotted time. Configurable name/polling fields still have known Core pylint policy warnings; this is not ready for an official Core PR. Physical-meter and real historical-database acceptance remain outstanding.

## Stop and revert

Stop the test process with Ctrl+C. Return to the original HA service and its original configuration. This procedure does not replace that service. Keep or remove only the separate checkout and test configuration as desired; do not point an older HA at the preview database. No official Core PR or PyPI release is part of this preview.
