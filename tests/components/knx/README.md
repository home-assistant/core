# Testing the KNX integration

A KNXTestKit instance can be requested from a fixture. It provides convenience methods
to test outgoing KNX telegrams and inject incoming telegrams.
To test something add a test function requesting the `hass` and `knx` fixture and
set up the KNX integration with `knx.setup_integration`.
You can pass a KNX YAML-config dict or a ConfigStore fixture filename to the setup method. The fixture should be placed in the `tests/components/knx/fixtures` directory.

```python
async def test_some_yaml(hass: HomeAssistant, knx: KNXTestKit):
    await knx.setup_integration(
        yaml_config={
            "switch": {
                "name": "test_switch",
                "address": "1/2/3",
            }
        }
    )

async def test_some_config_store(hass: HomeAssistant, knx: KNXTestKit):
    await knx.setup_integration(config_store_fixture="config_store_filename.json")
```

## Asserting outgoing telegrams

All outgoing telegrams are appended to an assertion list. Assert them in order they were sent or pass `ignore_order=True` to the assertion method.

- `knx.assert_no_telegram`
  Asserts that no telegram was sent (assertion list is empty).
- `knx.assert_telegram_count(count: int)`
  Asserts that `count` telegrams were sent.
- `knx.assert_read(group_address: str,  response: int | tuple[int, ...] | None = None, ignore_order: bool = False)`
  Asserts that a GroupValueRead telegram was sent to `group_address`.
  The telegram will be removed from the assertion list.
  Optionally inject incoming GroupValueResponse telegram after reception to clear the value reader waiting task. This can also be done manually with `knx.receive_response`.
- `knx.assert_response(group_address: str, payload: int | tuple[int, ...], ignore_order: bool = False)`
  Asserts that a GroupValueResponse telegram with `payload` was sent to `group_address`.
  The telegram will be removed from the assertion list.
- `knx.assert_write(group_address: str, payload: int | tuple[int, ...], ignore_order: bool = False)`
  Asserts that a GroupValueWrite telegram with `payload` was sent to `group_address`.
  The telegram will be removed from the assertion list.

Change some states or call some services and assert outgoing telegrams.

```python
    # turn on switch
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test_switch"}, blocking=True
    )
    # assert ON telegram
    await knx.assert_write("1/2/3", True)
```

## Injecting incoming telegrams

- `knx.receive_read(group_address: str)`
  Inject and process a GroupValueRead telegram addressed to `group_address`.
- `knx.receive_response(group_address: str, payload: int | tuple[int, ...])`
  Inject and process a GroupValueResponse telegram addressed to `group_address` containing `payload`.
- `knx.receive_write(group_address: str, payload: int | tuple[int, ...])`
  Inject and process a GroupValueWrite telegram addressed to `group_address` containing `payload`.

Receive some telegrams and assert state.

```python
    # receive OFF telegram
    await knx.receive_write("1/2/3", False)
    # assert OFF state
    state = hass.states.get("switch.test_switch")
    assert state.state is STATE_OFF
```

## Notes

- For `payload` in `assert_*` and `receive_*` use `int` for DPT 1, 2 and 3 payload values (DPTBinary) and `tuple` for other DPTs (DPTArray).
- `await self.hass.async_block_till_done()` is called before `KNXTestKit.assert_*` and after `KNXTestKit.receive_*` so you don't have to explicitly call it.
- Make sure to assert every outgoing telegram that was created in a test. `assert_no_telegram` is automatically called on teardown.
- Make sure to `knx.receive_response()` for every Read-request sent form StateUpdater, or to pass its timeout, to not have lingering tasks when finishing the tests.
