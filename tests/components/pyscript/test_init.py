"""Test the pyscript component."""
from ast import literal_eval
import asyncio
from datetime import datetime as dt

from homeassistant.components.pyscript import DOMAIN
import homeassistant.components.pyscript.trigger as trigger
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_STATE_CHANGED
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.setup import async_setup_component

from tests.async_mock import mock_open, patch


async def setup_script(hass, notify_q, now, source):
    """Initialize and load the given pyscript."""
    scripts = [
        "/some/config/dir/pyscript/hello.py",
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


async def test_setup_fails_on_no_dir(hass, caplog):
    """Test we fail setup when no dir found."""
    with patch("homeassistant.components.pyscript.os.path.isdir", return_value=False):
        res = await async_setup_component(hass, "pyscript", {})

    assert not res
    assert "Folder pyscript not found in configuration folder" in caplog.text


async def test_service_exists(hass):
    """Test discover, compile script and install a service."""

    await setup_script(
        hass,
        None,
        dt(2020, 7, 1, 11, 59, 59, 999999),
        """
@service
def func1():
    pass

def func2():
    pass
""",
    )
    assert hass.services.has_service("pyscript", "func1")
    assert hass.services.has_service("pyscript", "reload")
    assert not hass.services.has_service("pyscript", "func2")


async def test_service_description(hass):
    """Test service description defined in doc_string."""

    await setup_script(
        hass,
        None,
        dt(2020, 7, 1, 11, 59, 59, 999999),
        """
@service
def func_no_doc_string(param1=None):
    pass

@service
def func_simple_doc_string(param2=None, param3=None):
    \"\"\"This is func2_simple_doc_string.\"\"\"
    pass

@service
def func_yaml_doc_string(param2=None, param3=None):
    \"\"\"yaml
description: This is func_yaml_doc_string.
fields:
  param1:
    description: first argument
    example: 12
  param2:
    description: second argument
    example: 34
\"\"\"
    pass
""",
    )
    descriptions = await async_get_all_descriptions(hass)

    assert descriptions[DOMAIN]["func_no_doc_string"] == {
        "description": "pyscript function func_no_doc_string()",
        "fields": {"param1": {"description": "argument param1"}},
    }

    assert descriptions[DOMAIN]["func_simple_doc_string"] == {
        "description": "This is func2_simple_doc_string.",
        "fields": {
            "param2": {"description": "argument param2"},
            "param3": {"description": "argument param3"},
        },
    }

    assert descriptions[DOMAIN]["func_yaml_doc_string"] == {
        "description": "This is func_yaml_doc_string.",
        "fields": {
            "param1": {"description": "first argument", "example": "12"},
            "param2": {"description": "second argument", "example": "34"},
        },
    }


async def test_service_run(hass, caplog):
    """Test running a service with keyword arguments."""
    notify_q = asyncio.Queue(0)
    await setup_script(
        hass,
        notify_q,
        dt(2020, 7, 1, 11, 59, 59, 999999),
        """

@service
def func1(arg1=1, arg2=2):
    x = 1
    x = 2 * x + 3
    log.info(f"this is func1 x = {x}, arg1 = {arg1}, arg2 = {arg2}")
    pyscript.done = [x, arg1, arg2]

@service
def func2(**kwargs):
    x = 1
    x = 2 * x + 3
    log.info(f"this is func1 x = {x}, kwargs = {kwargs}")
    has2 = service.has_service("pyscript", "func2")
    has3 = service.has_service("pyscript", "func3")
    pyscript.done = [x, kwargs, has2, has3]

@service
def call_service(domain=None, name=None, **kwargs):
    service.call(domain, name, **kwargs)

""",
    )
    await hass.services.async_call("pyscript", "func1", {})
    ret = await wait_until_done(notify_q)
    assert literal_eval(ret) == [5, 1, 2]
    assert "this is func1 x = 5" in caplog.text

    await hass.services.async_call(
        "pyscript",
        "call_service",
        {"domain": "pyscript", "name": "func1", "arg1": "string1"},
    )
    ret = await wait_until_done(notify_q)
    assert literal_eval(ret) == [5, "string1", 2]

    await hass.services.async_call(
        "pyscript", "func1", {"arg1": "string1", "arg2": 123}
    )
    ret = await wait_until_done(notify_q)
    assert literal_eval(ret) == [5, "string1", 123]

    await hass.services.async_call(
        "pyscript", "call_service", {"domain": "pyscript", "name": "func2"}
    )
    ret = await wait_until_done(notify_q)
    assert literal_eval(ret) == [5, {}, 1, 0]

    await hass.services.async_call(
        "pyscript",
        "call_service",
        {"domain": "pyscript", "name": "func2", "arg1": "string1"},
    )
    ret = await wait_until_done(notify_q)
    assert literal_eval(ret) == [5, {"arg1": "string1"}, 1, 0]

    await hass.services.async_call(
        "pyscript", "func2", {"arg1": "string1", "arg2": 123}
    )
    ret = await wait_until_done(notify_q)
    assert literal_eval(ret) == [5, {"arg1": "string1", "arg2": 123}, 1, 0]


async def test_reload(hass, caplog):
    """Test reload."""
    notify_q = asyncio.Queue(0)
    now = dt(2020, 7, 1, 11, 59, 59, 999999)
    source0 = """
seq_num = 0

@time_trigger
def func_startup_sync():
    global seq_num

    seq_num += 1
    log.info(f"func_startup_sync setting pyscript.done = {seq_num}")
    pyscript.done = seq_num

@service
@state_trigger("pyscript.f1var1 == '1'")
def func1(var_name=None, value=None):
    global seq_num

    seq_num += 1
    log.info(f"func1 var = {var_name}, value = {value}")
    pyscript.done = [seq_num, var_name, int(value)]

"""
    source1 = """
seq_num = 10

@time_trigger
def func_startup_sync():
    global seq_num

    seq_num += 1
    log.info(f"func_startup_sync setting pyscript.done = {seq_num}")
    pyscript.done = seq_num

@service
@state_trigger("pyscript.f5var1 == '1'")
def func5(var_name=None, value=None):
    global seq_num

    seq_num += 1
    log.info(f"func5 var = {var_name}, value = {value}")
    pyscript.done = [seq_num, var_name, int(value)]

"""

    await setup_script(hass, notify_q, now, source0)

    #
    # run and reload 6 times with different sournce files to make sure seqNum
    # gets reset, autostart of func_startup_sync happens and triggers work each time
    #
    # first time: fire event to startup triggers and run func_startup_sync
    #
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    for i in range(6):
        if i & 1:
            seq_num = 10

            assert not hass.services.has_service("pyscript", "func1")
            assert hass.services.has_service("pyscript", "reload")
            assert hass.services.has_service("pyscript", "func5")

            seq_num += 1
            assert literal_eval(await wait_until_done(notify_q)) == seq_num

            seq_num += 1
            # initialize the trigger and active variables
            hass.states.async_set("pyscript.f5var1", 0)

            # try some values that shouldn't work, then one that does
            hass.states.async_set("pyscript.f5var1", "string")
            hass.states.async_set("pyscript.f5var1", 1)
            assert literal_eval(await wait_until_done(notify_q)) == [
                seq_num,
                "pyscript.f5var1",
                1,
            ]
            assert "func5 var = pyscript.f5var1, value = 1" in caplog.text
            next_source = source0

        else:
            seq_num = 0

            assert hass.services.has_service("pyscript", "func1")
            assert hass.services.has_service("pyscript", "reload")
            assert not hass.services.has_service("pyscript", "func5")

            seq_num += 1
            assert literal_eval(await wait_until_done(notify_q)) == seq_num

            seq_num += 1
            # initialize the trigger and active variables
            hass.states.async_set("pyscript.f1var1", 0)

            # try some values that shouldn't work, then one that does
            hass.states.async_set("pyscript.f1var1", "string")
            hass.states.async_set("pyscript.f1var1", 1)
            assert literal_eval(await wait_until_done(notify_q)) == [
                seq_num,
                "pyscript.f1var1",
                1,
            ]
            assert "func1 var = pyscript.f1var1, value = 1" in caplog.text
            next_source = source1

        #
        # now reload the other source file
        #
        scripts = [
            "/some/config/dir/pyscript/hello.py",
        ]
        with patch(
            "homeassistant.components.pyscript.os.path.isdir", return_value=True
        ), patch(
            "homeassistant.components.pyscript.glob.iglob", return_value=scripts
        ), patch(
            "homeassistant.components.pyscript.open",
            mock_open(read_data=next_source),
            create=True,
        ), patch(
            "homeassistant.components.pyscript.trigger.dt_now", return_value=now
        ):
            await hass.services.async_call("pyscript", "reload", {}, blocking=True)
