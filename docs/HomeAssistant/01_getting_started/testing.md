---
title: "Testing your code"
---

As stated in the [Style guidelines section](development_guidelines.md) all code is checked to verify the following:

- All the unit tests pass
- All code passes the checks from the linting tools

Local testing is done using [pytest](https://docs.pytest.org/) and using [prek](https://prek.j178.dev/) for running our linters, which has been installed as part of running `script/setup` in the [virtual environment](development_environment.mdx).

Python test requirements need to be installed before tests can be run. This can be achieved by using the VScode devcontainer and the corresponding task. Check the [devcontainer documentation](/docs/development_environment#tasks) for guidance about running tasks.

To run our linters, on the full code base, run the following command:

```shell
prek run --all-files
```

To run the full test suite, more dependencies are required than what is set up in the devcontainer by default. To install all dependencies, activate the virtual environment and run the command:

```shell
uv pip install -r requirements_test_all.txt
```

Or, in Visual Studio Code, launch the **Install all Test Requirements** task.

To start the tests, and run the full test suite, activate the virtual environment and run the command:

```shell
pytest tests
```

Or, in Visual Studio Code, launch the **Pytest** task.

It might be required that you install additional packages depending on your distribution/operating system:

- Fedora: `sudo dnf -y install systemd-devel gcc-c++`
- Ubuntu: `sudo apt-get install libudev-dev`

:::info Important
Run `pytest` & `prek` before you create your pull request to avoid annoying fixes.
`prek` will be invoked automatically by git when committing changes.
:::

:::note
Running the full `pytest` test suite will take quite some time, so as the minimal requirement for pull requests, run at least the tests that are related to your code changes (see details below on how to). The full test suite will anyway be run by the CI once you created your pull request and before it can be merged.
:::

Running `pytest` will run unit tests against the locally available Python version. We run our tests in our CI against all our supported Python versions.

### Adding new dependencies to test environment

If you are working on tests for an integration and you changed the dependencies, then run the `script/gen_requirements_all.py` script to update all requirement files.
Next you can update all dependencies in your development environment by running:

```shell
uv pip install -r requirements_test_all.txt
```

Or, in Visual Studio Code, launch the **Install all Test Requirements** task.

### Running a limited test suite

You can pass arguments to `pytest` to be able to run single test suites or test files.
Here are some helpful commands:

```shell
# Stop after the first test fails
$ pytest tests/test_core.py -x

# Run test with specified name
$ pytest tests/test_core.py -k test_split_entity_id

# Fail a test after it runs for 2 seconds
$ pytest tests/test_core.py --timeout 2

# Show the 10 slowest tests
$ pytest tests/test_core.py --duration=10
```

If you want to test just your integration, and include a test coverage report,
the following command is recommended:

```shell
pytest ./tests/components/<your_component>/ --cov=homeassistant.components.<your_component> --cov-report term-missing -vv
```

Or, in Visual Studio Code, launch the **Code Coverage** task.

### Preventing linter errors

Several linters are setup to run automatically when you try to commit as part of running `script/setup` in the [virtual environment](development_environment.mdx).

You can also run these linters manually :

```shell
prek run --show-diff-on-failure
```

Or, in Visual Studio Code, launch the **Prek** task.

The linters are also available directly, you can run tests on individual files:

```shell
ruff check homeassistant/core.py
pylint homeassistant/core.py
```

### Notes on PyLint and PEP8 validation

If you can't avoid a PyLint warning, add a comment to disable the PyLint check for that line with `# pylint: disable=YOUR-ERROR-NAME`. Example of an unavoidable one is if PyLint incorrectly reports that a certain object doesn't have a certain member.

### Writing tests for integrations

- Make sure to not interact with any integration details in tests of integrations. Following this pattern will make the tests more robust for changes in the integration.
  - Set up the integration with the core interface either [`async_setup_component`](https://github.com/home-assistant/core/blob/4cce724473233d4fb32c08bd251940b1ce2ba570/homeassistant/setup.py#L44-L46) or [`hass.config_entries.async_setup`](https://github.com/home-assistant/core/blob/4cce724473233d4fb32c08bd251940b1ce2ba570/homeassistant/config_entries.py#L693) if the integration supports config entries.
  - Assert the entity state via the core state machine [`hass.states`](https://github.com/home-assistant/core/blob/4cce724473233d4fb32c08bd251940b1ce2ba570/homeassistant/core.py#L887).
  - Perform service action calls via the core service registry [`hass.services`](https://github.com/home-assistant/core/blob/4cce724473233d4fb32c08bd251940b1ce2ba570/homeassistant/core.py#L1133).
  - Assert `DeviceEntry` state via the [device registry](https://github.com/home-assistant/core/blob/4cce724473233d4fb32c08bd251940b1ce2ba570/homeassistant/helpers/device_registry.py#L101).
  - Assert entity registry `RegistryEntry` state via the [entity registry](https://github.com/home-assistant/core/blob/4cce724473233d4fb32c08bd251940b1ce2ba570/homeassistant/helpers/entity_registry.py#L120).
  - Modify a `ConfigEntry` via the config entries interface [`hass.config_entries`](https://github.com/home-assistant/core/blob/4cce724473233d4fb32c08bd251940b1ce2ba570/homeassistant/config_entries.py#L570).
  - Assert the state of a config entry via the [`ConfigEntry.state`](https://github.com/home-assistant/core/blob/4cce724473233d4fb32c08bd251940b1ce2ba570/homeassistant/config_entries.py#L169) attribute.
  - Mock a config entry via the `MockConfigEntry` class in [`tests/common.py`](https://github.com/home-assistant/core/blob/4cce724473233d4fb32c08bd251940b1ce2ba570/tests/common.py#L658)

### Snapshot testing

Home Assistant supports a testing concept called snapshot testing (also known
as approval tests), which are tests that assert values against a stored
reference value (the snapshot).

Snapshot tests are different from regular (functional) tests and do not replace
functional tests, but they can be very useful for testing larger test outputs.
Within Home Assistant they could, for example, be used to:

- Ensure the output of an entity state is and remains as expected.
- Ensure an area, config, device, entity, or issue entry in the registry is and
  remains as expected.
- Ensure the output of a diagnostic dump is and remains as expected.
- Ensure a FlowResult is and remains as expected.

And many more cases that have large output, like JSON, YAML, or XML results.

The big difference between snapshot tests and regular tests is that the results
are captured by running the tests in a special mode that creates the snapshots.
Any sequential runs of the tests will then compare the results against the
snapshot. If the results are different, the test will fail.

Snapshot testing in Home Assistant is built on top of [Syrupy](https://github.com/tophat/syrupy),
their documentation can thus be applied when writing Home Assistant tests.
This is a snapshot test that asserts the output of an entity state:

```python
# tests/components/example/test_sensor.py
from homeassistant.core import HomeAssistant
from syrupy.assertion import SnapshotAssertion


async def test_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor state."""
    state = hass.states.get("sensor.whatever")
    assert state == snapshot
```

When this test is run for the first time, it will fail, as no snapshot exists.
To create (or update) a snapshot, run the test with
the `--snapshot-update` flag:

```shell
pytest tests/components/example/test_sensor.py --snapshot-update
```

Or, in Visual Studio Code, launch the **Update syrupy snapshots** task.

This will create a snapshot file in the `tests/components/example/snapshots`.
The snapshot file is named after the test file, in this case `test_sensor.ambr`,
and is human-readable. The snapshot files must be committed to the repository.

When the test is run again (without the update flag), it will compare the
results against the stored snapshot and everything should pass.

When the test results change, the test will fail and the snapshot needs to be
updated again.

Use snapshot testing with care! As it is very easy to create a snapshot,
it can be tempting to assert everything against a snapshot. However, remember,
it is not a replacement for functional tests.

As an example, when testing if an entity would go unavailable when the device
returns an error, it is better to assert the specific change you expected: 
Assert the state of the entity became `unavailable`. This functional test is a
better approach than asserting the full state of such an entity using a
snapshot, as it assumes it worked as expected (when taking the snapshot).
