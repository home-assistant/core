"""Test the python_script component."""

import logging
from unittest.mock import mock_open, patch

import pytest

from homeassistant.components.python_script import DOMAIN, FOLDER, execute
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.setup import async_setup_component

from tests.common import patch_yaml_files


async def test_setup(hass: HomeAssistant) -> None:
    """Test we can discover scripts."""
    scripts = [
        "/some/config/dir/python_scripts/hello.py",
        "/some/config/dir/python_scripts/world_beer.py",
    ]
    with (
        patch(
            "homeassistant.components.python_script.os.path.isdir", return_value=True
        ),
        patch(
            "homeassistant.components.python_script.glob.iglob", return_value=scripts
        ),
    ):
        res = await async_setup_component(hass, "python_script", {})

    assert res
    assert hass.services.has_service("python_script", "hello")
    assert hass.services.has_service("python_script", "world_beer")

    with (
        patch(
            "homeassistant.components.python_script.open",
            mock_open(read_data="fake source"),
            create=True,
        ),
        patch("homeassistant.components.python_script.execute") as mock_ex,
    ):
        await hass.services.async_call(
            "python_script", "hello", {"some": "data"}, blocking=True
        )

    assert len(mock_ex.mock_calls) == 1
    test_hass, script, source, data = mock_ex.mock_calls[0][1]

    assert test_hass is hass
    assert script == "hello.py"
    assert source == "fake source"
    assert data == {"some": "data"}


async def test_setup_fails_on_no_dir(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we fail setup when no dir found."""
    with patch(
        "homeassistant.components.python_script.os.path.isdir", return_value=False
    ):
        res = await async_setup_component(hass, "python_script", {})

    assert not res
    assert "Folder python_scripts not found in configuration folder" in caplog.text


async def test_execute_with_data(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test executing a script."""
    caplog.set_level(logging.WARNING)
    source = """
hass.states.set('test.entity', data.get('name', 'not set'))
    """

    hass.async_add_executor_job(execute, hass, "test.py", source, {"name": "paulus"})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.is_state("test.entity", "paulus")

    # No errors logged = good
    assert caplog.text == ""


async def test_execute_warns_print(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test print triggers warning."""
    caplog.set_level(logging.WARNING)
    source = """
print("This triggers warning.")
    """

    hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Don't use print() inside scripts." in caplog.text


async def test_execute_logging(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test logging works."""
    caplog.set_level(logging.INFO)
    source = """
logger.info('Logging from inside script')
    """

    hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Logging from inside script" in caplog.text


async def test_execute_compile_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test compile error logs error."""
    caplog.set_level(logging.ERROR)
    source = """
this is not valid Python
    """

    hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Error loading script test.py" in caplog.text


async def test_execute_runtime_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test compile error logs error."""
    caplog.set_level(logging.ERROR)
    source = """
raise Exception('boom')
    """

    await hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Error executing script" in caplog.text


async def test_execute_runtime_error_with_response(hass: HomeAssistant) -> None:
    """Test compile error logs error."""
    source = """
raise Exception('boom')
    """

    task = hass.async_add_executor_job(execute, hass, "test.py", source, {}, True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert type(task.exception()) is HomeAssistantError
    assert "Error executing script (Exception): boom" in str(task.exception())


async def test_accessing_async_methods(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test compile error logs error."""
    caplog.set_level(logging.ERROR)
    source = """
hass.async_stop()
    """

    await hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done()

    assert "Not allowed to access async methods" in caplog.text


async def test_accessing_async_methods_with_response(hass: HomeAssistant) -> None:
    """Test compile error logs error."""
    source = """
hass.async_stop()
    """

    task = hass.async_add_executor_job(execute, hass, "test.py", source, {}, True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert type(task.exception()) is ServiceValidationError
    assert "Not allowed to access async methods" in str(task.exception())


async def test_using_complex_structures(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that dicts and lists work."""
    caplog.set_level(logging.INFO)
    source = """
mydict = {"a": 1, "b": 2}
mylist = [1, 2, 3, 4]
logger.info('Logging from inside script: %s %s' % (mydict["a"], mylist[2]))
    """

    await hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done()

    assert "Logging from inside script: 1 3" in caplog.text


async def test_accessing_forbidden_methods(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test compile error logs error."""
    caplog.set_level(logging.ERROR)

    for source, name in {
        "hass.stop()": "HomeAssistant.stop",
        "dt_util.set_default_time_zone()": "module.set_default_time_zone",
        "datetime.non_existing": "module.non_existing",
        "time.tzset()": "TimeWrapper.tzset",
    }.items():
        caplog.records.clear()
        await hass.async_add_executor_job(execute, hass, "test.py", source, {})
        await hass.async_block_till_done()
        assert f"Not allowed to access {name}" in caplog.text


async def test_accessing_forbidden_methods_with_response(hass: HomeAssistant) -> None:
    """Test compile error logs error."""
    for source, name in {
        "hass.stop()": "HomeAssistant.stop",
        "dt_util.set_default_time_zone()": "module.set_default_time_zone",
        "datetime.non_existing": "module.non_existing",
        "time.tzset()": "TimeWrapper.tzset",
    }.items():
        task = hass.async_add_executor_job(execute, hass, "test.py", source, {}, True)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert type(task.exception()) is ServiceValidationError
        assert f"Not allowed to access {name}" in str(task.exception())


async def test_iterating(hass: HomeAssistant) -> None:
    """Test compile error logs error."""
    source = """
for i in [1, 2]:
    hass.states.set('hello.{}'.format(i), 'world')
    """

    await hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done()

    assert hass.states.is_state("hello.1", "world")
    assert hass.states.is_state("hello.2", "world")


async def test_using_enumerate(hass: HomeAssistant) -> None:
    """Test that enumerate is accepted and executed."""
    source = """
for index, value in enumerate(["earth", "mars"]):
    hass.states.set('hello.{}'.format(index), value)
    """

    await hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done()

    assert hass.states.is_state("hello.0", "earth")
    assert hass.states.is_state("hello.1", "mars")


async def test_unpacking_sequence(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test compile error logs error."""
    caplog.set_level(logging.ERROR)
    source = """
a,b = (1,2)
ab_list = [(a,b) for a,b in [(1, 2), (3, 4)]]
hass.states.set('hello.a', a)
hass.states.set('hello.b', b)
hass.states.set('hello.ab_list', '{}'.format(ab_list))
"""

    hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.is_state("hello.a", "1")
    assert hass.states.is_state("hello.b", "2")
    assert hass.states.is_state("hello.ab_list", "[(1, 2), (3, 4)]")

    # No errors logged = good
    assert caplog.text == ""


async def test_execute_sorted(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test sorted() function."""
    caplog.set_level(logging.ERROR)
    source = """
a  = sorted([3,1,2])
assert(a == [1,2,3])
hass.states.set('hello.a', a[0])
hass.states.set('hello.b', a[1])
hass.states.set('hello.c', a[2])
"""
    hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.is_state("hello.a", "1")
    assert hass.states.is_state("hello.b", "2")
    assert hass.states.is_state("hello.c", "3")
    # No errors logged = good
    assert caplog.text == ""


async def test_exposed_modules(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test datetime and time modules exposed."""
    caplog.set_level(logging.ERROR)
    source = """
hass.states.set('module.time', time.strftime('%Y', time.gmtime(521276400)))
hass.states.set('module.time_strptime',
                time.strftime('%H:%M', time.strptime('12:34', '%H:%M')))
hass.states.set('module.datetime',
                datetime.timedelta(minutes=1).total_seconds())
"""

    hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.is_state("module.time", "1986")
    assert hass.states.is_state("module.time_strptime", "12:34")
    assert hass.states.is_state("module.datetime", "60.0")

    # No errors logged = good
    assert caplog.text == ""


async def test_execute_functions(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test functions defined in script can call one another."""
    caplog.set_level(logging.ERROR)
    source = """
def a():
    hass.states.set('hello.a', 'one')

def b():
    a()
    hass.states.set('hello.b', 'two')

b()
"""
    hass.async_add_executor_job(execute, hass, "test.py", source, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.is_state("hello.a", "one")
    assert hass.states.is_state("hello.b", "two")
    # No errors logged = good
    assert caplog.text == ""


async def test_reload(hass: HomeAssistant) -> None:
    """Test we can re-discover scripts."""
    scripts = [
        "/some/config/dir/python_scripts/hello.py",
        "/some/config/dir/python_scripts/world_beer.py",
    ]
    with (
        patch(
            "homeassistant.components.python_script.os.path.isdir", return_value=True
        ),
        patch(
            "homeassistant.components.python_script.glob.iglob", return_value=scripts
        ),
    ):
        res = await async_setup_component(hass, "python_script", {})

    assert res
    assert hass.services.has_service("python_script", "hello")
    assert hass.services.has_service("python_script", "world_beer")
    assert hass.services.has_service("python_script", "reload")

    scripts = [
        "/some/config/dir/python_scripts/hello2.py",
        "/some/config/dir/python_scripts/world_beer.py",
    ]
    with (
        patch(
            "homeassistant.components.python_script.os.path.isdir", return_value=True
        ),
        patch(
            "homeassistant.components.python_script.glob.iglob", return_value=scripts
        ),
    ):
        await hass.services.async_call("python_script", "reload", {}, blocking=True)

    assert not hass.services.has_service("python_script", "hello")
    assert hass.services.has_service("python_script", "hello2")
    assert hass.services.has_service("python_script", "world_beer")
    assert hass.services.has_service("python_script", "reload")


async def test_service_descriptions(hass: HomeAssistant) -> None:
    """Test that service descriptions are loaded and reloaded correctly."""
    # Test 1: no user-provided services.yaml file
    scripts1 = [
        "/some/config/dir/python_scripts/hello.py",
        "/some/config/dir/python_scripts/world_beer.py",
    ]

    service_descriptions1 = (
        "hello:\n"
        "  name: ABC\n"
        "  description: Description of hello.py.\n"
        "  fields:\n"
        "    fake_param:\n"
        "      description: Parameter used by hello.py.\n"
        "      example: 'This is a test of python_script.hello'"
    )
    services_yaml1 = {
        f"{hass.config.config_dir}/{FOLDER}/services.yaml": service_descriptions1
    }

    with (
        patch(
            "homeassistant.components.python_script.os.path.isdir", return_value=True
        ),
        patch(
            "homeassistant.components.python_script.glob.iglob", return_value=scripts1
        ),
        patch(
            "homeassistant.components.python_script.os.path.exists", return_value=True
        ),
        patch_yaml_files(
            services_yaml1,
        ),
    ):
        await async_setup_component(hass, DOMAIN, {})

        descriptions = await async_get_all_descriptions(hass)

    assert len(descriptions) == 1

    assert descriptions[DOMAIN]["hello"]["name"] == "ABC"
    assert descriptions[DOMAIN]["hello"]["description"] == "Description of hello.py."
    assert (
        descriptions[DOMAIN]["hello"]["fields"]["fake_param"]["description"]
        == "Parameter used by hello.py."
    )
    assert (
        descriptions[DOMAIN]["hello"]["fields"]["fake_param"]["example"]
        == "This is a test of python_script.hello"
    )

    # Verify default name = file name
    assert descriptions[DOMAIN]["world_beer"]["name"] == "world_beer"
    assert descriptions[DOMAIN]["world_beer"]["description"] == ""
    assert bool(descriptions[DOMAIN]["world_beer"]["fields"]) is False

    # Test 2: user-provided services.yaml file
    scripts2 = [
        "/some/config/dir/python_scripts/hello2.py",
        "/some/config/dir/python_scripts/world_beer.py",
    ]

    service_descriptions2 = (
        "hello2:\n"
        "  description: Description of hello2.py.\n"
        "  fields:\n"
        "    fake_param:\n"
        "      description: Parameter used by hello2.py.\n"
        "      example: 'This is a test of python_script.hello2'"
    )
    services_yaml2 = {
        f"{hass.config.config_dir}/{FOLDER}/services.yaml": service_descriptions2
    }

    with (
        patch(
            "homeassistant.components.python_script.os.path.isdir", return_value=True
        ),
        patch(
            "homeassistant.components.python_script.glob.iglob", return_value=scripts2
        ),
        patch(
            "homeassistant.components.python_script.os.path.exists", return_value=True
        ),
        patch_yaml_files(
            services_yaml2,
        ),
    ):
        await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
        descriptions = await async_get_all_descriptions(hass)

    assert len(descriptions) == 1

    assert descriptions[DOMAIN]["hello2"]["description"] == "Description of hello2.py."
    assert (
        descriptions[DOMAIN]["hello2"]["fields"]["fake_param"]["description"]
        == "Parameter used by hello2.py."
    )
    assert (
        descriptions[DOMAIN]["hello2"]["fields"]["fake_param"]["example"]
        == "This is a test of python_script.hello2"
    )


async def test_sleep_warns_one(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test time.sleep warns once."""
    caplog.set_level(logging.WARNING)
    source = """
time.sleep(2)
time.sleep(5)
"""

    with patch("homeassistant.components.python_script.time.sleep"):
        hass.async_add_executor_job(execute, hass, "test.py", source, {})
        await hass.async_block_till_done(wait_background_tasks=True)

    assert caplog.text.count("time.sleep") == 1


async def test_execute_with_output(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test executing a script with a return value."""
    caplog.set_level(logging.WARNING)

    scripts = [
        "/some/config/dir/python_scripts/hello.py",
    ]
    with (
        patch(
            "homeassistant.components.python_script.os.path.isdir", return_value=True
        ),
        patch(
            "homeassistant.components.python_script.glob.iglob", return_value=scripts
        ),
    ):
        await async_setup_component(hass, "python_script", {})

    source = """
output = {"result": f"hello {data.get('name', 'World')}"}
    """

    with patch(
        "homeassistant.components.python_script.open",
        mock_open(read_data=source),
        create=True,
    ):
        response = await hass.services.async_call(
            "python_script",
            "hello",
            {"name": "paulus"},
            blocking=True,
            return_response=True,
        )

    assert isinstance(response, dict)
    assert len(response) == 1
    assert response["result"] == "hello paulus"

    # No errors logged = good
    assert caplog.text == ""


async def test_execute_no_output(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test executing a script without a return value."""
    caplog.set_level(logging.WARNING)

    scripts = [
        "/some/config/dir/python_scripts/hello.py",
    ]
    with (
        patch(
            "homeassistant.components.python_script.os.path.isdir", return_value=True
        ),
        patch(
            "homeassistant.components.python_script.glob.iglob", return_value=scripts
        ),
    ):
        await async_setup_component(hass, "python_script", {})

    source = """
no_output = {"result": f"hello {data.get('name', 'World')}"}
    """

    with patch(
        "homeassistant.components.python_script.open",
        mock_open(read_data=source),
        create=True,
    ):
        response = await hass.services.async_call(
            "python_script",
            "hello",
            {"name": "paulus"},
            blocking=True,
            return_response=True,
        )

    assert isinstance(response, dict)
    assert len(response) == 0

    # No errors logged = good
    assert caplog.text == ""


async def test_execute_wrong_output_type(hass: HomeAssistant) -> None:
    """Test executing a script without a return value."""
    scripts = [
        "/some/config/dir/python_scripts/hello.py",
    ]
    with (
        patch(
            "homeassistant.components.python_script.os.path.isdir", return_value=True
        ),
        patch(
            "homeassistant.components.python_script.glob.iglob", return_value=scripts
        ),
    ):
        await async_setup_component(hass, "python_script", {})

    source = """
output = f"hello {data.get('name', 'World')}"
    """

    with (
        patch(
            "homeassistant.components.python_script.open",
            mock_open(read_data=source),
            create=True,
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            "python_script",
            "hello",
            {"name": "paulus"},
            blocking=True,
            return_response=True,
        )


async def test_augmented_assignment_operations(hass: HomeAssistant) -> None:
    """Test that augmented assignment operations work."""
    source = """
a = 10
a += 20
a *= 5
a -= 8
b = "foo"
b += "bar"
b *= 2
c = []
c += [1, 2, 3]
c *= 2
hass.states.set('hello.a', a)
hass.states.set('hello.b', b)
hass.states.set('hello.c', c)
    """

    hass.async_add_executor_job(execute, hass, "aug_assign.py", source, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("hello.a").state == str(((10 + 20) * 5) - 8)
    assert hass.states.get("hello.b").state == ("foo" + "bar") * 2
    assert hass.states.get("hello.c").state == str([1, 2, 3] * 2)


@pytest.mark.parametrize(
    ("case", "error"),
    [
        pytest.param(
            "d = datetime.date(2024, 1, 1); d += 5",
            "The '+=' operation is not allowed",
            id="datetime.date",
        ),
    ],
)
async def test_prohibited_augmented_assignment_operations(
    hass: HomeAssistant, case: str, error: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that prohibited augmented assignment operations raise an error."""
    hass.async_add_executor_job(execute, hass, "aug_assign_prohibited.py", case, {})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert error in caplog.text
