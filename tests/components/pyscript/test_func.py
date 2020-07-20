"""Test the pyscript component."""
from ast import literal_eval
import asyncio
from datetime import datetime as dt
import time

import homeassistant.components.pyscript.trigger as trigger
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_STATE_CHANGED
from homeassistant.setup import async_setup_component

from tests.async_mock import mock_open, patch


async def setup_script(hass, notify_q, now, source):
    """Initialize and load the given pyscript."""
    scripts = [
        "/some/config/dir/pyscripts/hello.py",
    ]
    with patch(
        "homeassistant.components.pyscript.os.path.isdir", return_value=True
    ), patch(
        "homeassistant.components.pyscript.glob.iglob", return_value=scripts
    ), patch(
        "homeassistant.components.pyscript.open",
        mock_open(read_data=source),
        create=True,
    ), patch(
        "homeassistant.components.pyscript.trigger.dt_now", return_value=now
    ):
        assert await async_setup_component(hass, "pyscript", {})

    #
    # I'm not sure how to run the mock all the time, so just force the dt_now()
    # trigger function to return the fixed time, now.
    #
    trigger.__dict__["dt_now"] = lambda: now

    if notify_q:

        async def state_changed(event):
            var_name = event.data["entity_id"]
            if var_name != "pyscript.done":
                return
            value = event.data["new_state"].state
            await notify_q.put(value)

        hass.bus.async_listen(EVENT_STATE_CHANGED, state_changed)


async def wait_until_done(notify_q):
    """Wait for the done handshake."""
    return await asyncio.wait_for(notify_q.get(), timeout=4)


async def test_state_trigger(hass, caplog):
    """Test state trigger."""
    notify_q = asyncio.Queue(0)
    await setup_script(
        hass,
        notify_q,
        dt(2020, 7, 1, 11, 59, 59, 999999),
        """

from math import sqrt

seq_num = 0

@time_trigger
def func_startup_sync():
    global seq_num

    seq_num += 1
    log.info(f"func_startup_sync setting pyscript.done = {seq_num}")
    pyscript.done = seq_num

@state_trigger("pyscript.f1var1 == '1'")
def func1(var_name=None, value=None):
    global seq_num

    seq_num += 1
    log.info(f"func1 var = {var_name}, value = {value}")
    pyscript.done = [seq_num, var_name, int(value), sqrt(1024)]

@state_trigger("pyscript.f1var1 == '1' or pyscript.f2var2 == '2'")
@state_active("pyscript.f2var3 == '3' and pyscript.f2var4 == '4'")
def func2(var_name=None, value=None):
    global seq_num

    seq_num += 1
    log.info(f"func2 var = {var_name}, value = {value}")
    pyscript.done = [seq_num, var_name, int(value), sqrt(4096)]

@event_trigger("fire_event")
def fire_event(**kwargs):
    event.fire(kwargs["new_event"], arg1=kwargs["arg1"], arg2=kwargs["arg2"])

@event_trigger("test_event3", "arg1 == 20 and arg2 == 30")
def func3(trigger_type=None, event_type=None, **kwargs):
    global seq_num

    seq_num += 1
    log.info(f"func3 trigger_type = {trigger_type}, event_type = {event_type}, event_data = {kwargs}")
    pyscript.done = [seq_num, trigger_type, event_type, kwargs]

@event_trigger("test_event4", "arg1 == 20 and arg2 == 30")
def func4(trigger_type=None, event_type=None, **kwargs):
    global seq_num

    seq_num += 1
    res = task.wait_until(event_trigger=["test_event4b", "arg1 == 25 and arg2 == 35"], timeout=10)
    log.info(f"func4 trigger_type = {res}, event_type = {event_type}, event_data = {kwargs}")
    pyscript.done = [seq_num, res, event_type, kwargs]

    seq_num += 1
    res = task.wait_until(state_trigger="pyscript.f4var2 == '2'", timeout=10)
    log.info(f"func4 trigger_type = {res}")
    pyscript.done = [seq_num, res]

    pyscript.setVar1 = 1
    pyscript.setVar2 = "var2"
    state.set("pyscript.setVar3", {"foo": "bar"})
    state.set("pyscript.setVar1", 1 + int(state.get("pyscript.setVar1")), {"attr1": 456, "attr2": 987})

    seq_num += 1
    res = task.wait_until(state_trigger="pyscript.f4var2 == '10'", timeout=10)
    log.info(f"func4 trigger_type = {res}")
    pyscript.done = [seq_num, res, pyscript.setVar1, pyscript.setVar1.attr1, state.get("pyscript.setVar1.attr2"), pyscript.setVar2, state.get("pyscript.setVar3")]

    seq_num += 1
    #
    # now() returns 1usec before 2020/7/1 12:00:00, so trigger right
    # at noon
    #
    res = task.wait_until(time_trigger="once(2020/07/01 12:00:00)", timeout=10)
    log.info(f"func4 trigger_type = {res}")
    pyscript.done = [seq_num, res]

    seq_num += 1
    #
    # this should pick up the trigger interval at noon
    #
    res = task.wait_until(time_trigger="period(2020/07/01 11:00, 1 hour)", timeout=10)
    log.info(f"func4 trigger_type = {res}")
    pyscript.done = [seq_num, res]

    seq_num += 1
    #
    # cron triggers at 10am, 11am, noon, 1pm, 2pm, 3pm, so this
    # should trigger at noon.
    #
    res = task.wait_until(time_trigger="cron(0 10-15 * * *)", timeout=10)
    log.info(f"func4 trigger_type = {res}")
    pyscript.done = [seq_num, res]

    seq_num += 1
    #
    # also add some month and day ranges; should still trigger at noon
    # on 7/1.
    #
    res = task.wait_until(time_trigger="cron(0 10-15 1-5 6,7 *)", timeout=10)
    log.info(f"func4 trigger_type = {res}")
    pyscript.done = [seq_num, res]

    seq_num += 1
    #
    # make sure a short timeout works, for a trigger further out in time
    # (7/5 at 3pm)
    #
    res = task.wait_until(time_trigger="cron(0 15 5 6,7 *)", timeout=1e-6)
    log.info(f"func4 trigger_type = {res}")
    pyscript.done = [seq_num, res]

    seq_num += 1
    #
    # make sure a short timeout works when there are no other triggers
    #
    res = task.wait_until(timeout=1e-6)
    log.info(f"func4 trigger_type = {res}")
    pyscript.done = [seq_num, res]

    seq_num += 1
    #
    # make sure we return when there no triggers and no timeout
    #
    res = task.wait_until()
    log.info(f"func4 trigger_type = {res}")
    pyscript.done = [seq_num, res]

    seq_num += 1
    #
    # make sure we return when there only past triggers and no timeout
    #
    res = task.wait_until(time_trigger="once(2020/7/1 11:59:59.999)")
    log.info(f"func4 trigger_type = {res}")
    pyscript.done = [seq_num, res]

    #
    # create a run-time exception
    #
    no_such_function("xyz")

""",
    )
    seq_num = 0

    seq_num += 1
    # fire event to startup triggers, and handshake when they are running
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    assert literal_eval(await wait_until_done(notify_q)) == seq_num

    seq_num += 1
    # initialize the trigger and active variables
    hass.states.async_set("pyscript.f1var1", 0)
    hass.states.async_set("pyscript.f2var2", 0)
    hass.states.async_set("pyscript.f2var3", 0)
    hass.states.async_set("pyscript.f2var4", 0)

    # try some values that shouldn't work, then one that does
    hass.states.async_set("pyscript.f1var1", 0)
    hass.states.async_set("pyscript.f1var1", "string")
    hass.states.async_set("pyscript.f1var1", -1)
    hass.states.async_set("pyscript.f1var1", 1)
    assert literal_eval(await wait_until_done(notify_q)) == [
        seq_num,
        "pyscript.f1var1",
        1,
        32,
    ]
    assert "func1 var = pyscript.f1var1, value = 1" in caplog.text

    seq_num += 1
    hass.states.async_set("pyscript.f2var3", 3)
    hass.states.async_set("pyscript.f2var4", 0)
    hass.states.async_set("pyscript.f2var2", 0)
    hass.states.async_set("pyscript.f1var1", 0)
    hass.states.async_set("pyscript.f1var1", 1)
    assert literal_eval(await wait_until_done(notify_q)) == [
        seq_num,
        "pyscript.f1var1",
        1,
        32,
    ]

    seq_num += 1
    hass.states.async_set("pyscript.f2var4", 4)
    hass.states.async_set("pyscript.f2var2", 2)
    assert literal_eval(await wait_until_done(notify_q)) == [
        seq_num,
        "pyscript.f2var2",
        2,
        64,
    ]
    assert "func2 var = pyscript.f2var2, value = 2" in caplog.text

    seq_num += 1
    hass.bus.async_fire("test_event3", {"arg1": 12, "arg2": 34})
    hass.bus.async_fire("test_event3", {"arg1": 20, "arg2": 29})
    hass.bus.async_fire("test_event3", {"arg1": 12, "arg2": 30})
    hass.bus.async_fire(
        "fire_event", {"new_event": "test_event3", "arg1": 20, "arg2": 30}
    )
    assert literal_eval(await wait_until_done(notify_q)) == [
        seq_num,
        "event",
        "test_event3",
        {"arg1": 20, "arg2": 30},
    ]

    seq_num += 1
    hass.states.async_set("pyscript.f4var2", 2)
    hass.bus.async_fire("test_event4", {"arg1": 20, "arg2": 30})
    t_now = time.monotonic()
    while notify_q.empty() and time.monotonic() < t_now + 4:
        hass.bus.async_fire("test_event4b", {"arg1": 15, "arg2": 25})
        hass.bus.async_fire("test_event4b", {"arg1": 20, "arg2": 25})
        hass.bus.async_fire("test_event4b", {"arg1": 25, "arg2": 35})
        await asyncio.sleep(1e-3)
    trig = {
        "trigger_type": "event",
        "event_type": "test_event4b",
        "arg1": 25,
        "arg2": 35,
    }
    assert literal_eval(await wait_until_done(notify_q)) == [
        seq_num,
        trig,
        "test_event4",
        {"arg1": 20, "arg2": 30},
    ]

    seq_num += 1
    # the state_trigger wait_until should succeed immediately, since the expr is true
    assert literal_eval(await wait_until_done(notify_q)) == [
        seq_num,
        {"trigger_type": "state"},
    ]

    seq_num += 1
    # now try a few other values, then the correct one
    hass.states.async_set("pyscript.f4var2", 4)
    hass.states.async_set("pyscript.f4var2", 2)
    hass.states.async_set("pyscript.f4var2", 10)
    trig = {
        "trigger_type": "state",
        "var_name": "pyscript.f4var2",
        "value": "10",
        "old_value": "2",
    }
    result = literal_eval(await wait_until_done(notify_q))
    assert result[0] == seq_num
    assert result[1] == trig
    assert result[2:5] == ["2", 456, 987]

    assert hass.states.get("pyscript.setVar1").state == "2"
    assert hass.states.get("pyscript.setVar1").attributes == {
        "attr1": 456,
        "attr2": 987,
    }
    assert hass.states.get("pyscript.setVar2").state == "var2"
    assert literal_eval(hass.states.get("pyscript.setVar3").state) == {"foo": "bar"}

    #
    # check for the three time triggers, two timeouts and two none
    #
    for trig_type in ["time"] * 4 + ["timeout"] * 2 + ["none"] * 2:
        seq_num += 1
        assert literal_eval(await wait_until_done(notify_q)) == [
            seq_num,
            {"trigger_type": trig_type},
        ]

    assert "name 'no_such_function' is not defined" in caplog.text
