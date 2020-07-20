"""Component to allow running Python scripts."""

from collections import OrderedDict
import glob
import io
import logging
import os

import yaml

from homeassistant.components.pyscript.eval import AstEval, EvalFunc
from homeassistant.components.pyscript.event import Event
from homeassistant.components.pyscript.handler import Handler
from homeassistant.components.pyscript.state import State
from homeassistant.components.pyscript.trigger import TrigInfo, TrigTime
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    SERVICE_RELOAD,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DOMAIN = "pyscript"

FOLDER = "pyscript"


async def async_setup(hass, config):
    """Initialize the pyscript component."""

    handler_func = Handler(hass)
    event_func = Event(hass)
    trig_time_func = TrigTime(hass, handler_func)
    state_func = State(hass, handler_func)
    state_func.register_functions()

    path = hass.config.path(FOLDER)

    def check_isdir(path):
        return os.path.isdir(path)

    if not await hass.async_add_executor_job(check_isdir, path):
        _LOGGER.error("Folder %s not found in configuration folder", FOLDER)
        return False

    triggers, services = await compile_scripts(  # pylint: disable=unused-variable
        hass,
        event_func=event_func,
        state_func=state_func,
        handler_func=handler_func,
        trig_time_func=trig_time_func,
    )

    _LOGGER.debug("adding reload handler")

    async def reload_scripts_handler(call):
        """Handle reload service calls."""
        nonlocal triggers, services

        _LOGGER.debug(
            "stopping triggers and services, reloading scripts, and restarting"
        )
        for trig in triggers.values():
            await trig.stop()
        for name in services:
            hass.services.async_remove(DOMAIN, name)
        triggers, services = await compile_scripts(
            hass,
            event_func=event_func,
            state_func=state_func,
            handler_func=handler_func,
            trig_time_func=trig_time_func,
        )
        for trig in triggers.values():
            trig.start()

    hass.services.async_register(DOMAIN, SERVICE_RELOAD, reload_scripts_handler)

    async def state_changed(event):
        var_name = event.data["entity_id"]
        # attr = event.data["new_state"].attributes
        new_val = event.data["new_state"].state
        old_val = event.data["old_state"].state if event.data["old_state"] else None
        new_vars = {var_name: new_val, f"{var_name}.old": old_val}
        func_args = {
            "trigger_type": "state",
            "var_name": var_name,
            "value": new_val,
            "old_value": old_val,
        }
        await state_func.update(new_vars, func_args)

    async def start_triggers(event):
        _LOGGER.debug("adding state changed listener")
        hass.bus.async_listen(EVENT_STATE_CHANGED, state_changed)
        _LOGGER.debug("starting triggers")
        for trig in triggers.values():
            trig.start()

    async def stop_triggers(event):
        _LOGGER.debug("stopping triggers")
        for trig in triggers.values():
            await trig.stop()

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STARTED, start_triggers)
    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, stop_triggers)

    return True


@bind_hass
async def compile_scripts(
    hass, event_func=None, state_func=None, handler_func=None, trig_time_func=None
):
    """Compile all python scripts in FOLDER."""

    path = hass.config.path(FOLDER)

    _LOGGER.debug("compile_scripts: path = %s", path)

    def pyscript_service_factory(name, func, sym_table):
        async def pyscript_service_handler(call):
            """Handle python script service calls."""
            # ignore call.service
            _LOGGER.debug("service call to %s", name)
            #
            # use a new AstEval context so it can run fully independently
            # of other instances (except for global_sym_table which is common)
            #
            ast_ctx = AstEval(
                name,
                global_sym_table=sym_table,
                state_func=state_func,
                event_func=event_func,
                handler_func=handler_func,
            )
            handler_func.install_ast_funcs(ast_ctx)
            func_args = {
                "trigger_type": "service",
            }
            func_args = func_args.update(call.data)
            handler_func.create_task(func.call(ast_ctx, [], call.data))

        return pyscript_service_handler

    triggers = {}
    services = set()

    def glob_files(path, match):
        return glob.iglob(os.path.join(path, match))

    def read_file(path):
        with open(path) as file_desc:
            source = file_desc.read()
        return source

    source_files = await hass.async_add_executor_job(glob_files, path, "*.py")

    for file in source_files:
        _LOGGER.debug("reading and parsing %s", file)
        name = os.path.splitext(os.path.basename(file))[0]
        source = await hass.async_add_executor_job(read_file, file)

        global_sym_table = {}
        ast_ctx = AstEval(
            name,
            global_sym_table=global_sym_table,
            state_func=state_func,
            event_func=event_func,
            handler_func=handler_func,
        )
        handler_func.install_ast_funcs(ast_ctx)
        if not ast_ctx.parse(source, filename=file):
            continue
        await ast_ctx.eval()

        for name, func in global_sym_table.items():
            _LOGGER.debug("global_sym_table got %s, %s", name, func)
            if not isinstance(func, EvalFunc):
                continue
            if name == SERVICE_RELOAD:
                _LOGGER.error(
                    "function '%s' in %s conflicts with %s service; ignoring (please rename)",
                    name,
                    file,
                    SERVICE_RELOAD,
                )
                continue
            desc = func.get_doc_string()
            if desc is None or desc == "":
                desc = f"pyscript function {name}()"
            desc = desc.lstrip(" \n\r")
            if desc.startswith("yaml"):
                try:
                    desc = desc[4:].lstrip(" \n\r")
                    file_desc = io.StringIO(desc)
                    service_desc = (
                        yaml.load(file_desc, Loader=yaml.BaseLoader) or OrderedDict()
                    )
                    file_desc.close()
                except Exception as exc:
                    _LOGGER.error(
                        "Unable to decode yaml doc_string for %s(): %s", name, str(exc)
                    )
                    raise HomeAssistantError(exc)
            else:
                fields = OrderedDict()
                for arg in func.get_positional_args():
                    fields[arg] = OrderedDict(description=f"argument {arg}")
                service_desc = {"description": desc, "fields": fields}

            trig_args = {}
            trig_decorators = {
                "time_trigger",
                "state_trigger",
                "event_trigger",
                "state_active",
                "time_active",
            }
            for dec in func.get_decorators():
                dec_name, dec_args = dec[0], dec[1]
                if dec_name in trig_decorators:
                    if dec_name not in trig_args:
                        trig_args[dec_name] = []
                    if dec_args is not None:
                        trig_args[dec_name] += dec_args
                elif dec_name == "service":
                    if dec_args is not None:
                        _LOGGER.error(
                            "%s defined in %s: decorator @service takes no arguments; ignored",
                            name,
                            file,
                        )
                        continue
                    _LOGGER.debug(
                        "registering %s/%s (desc = %s)", DOMAIN, name, service_desc
                    )
                    hass.services.async_register(
                        DOMAIN,
                        name,
                        pyscript_service_factory(name, func, global_sym_table),
                    )
                    async_set_service_schema(hass, DOMAIN, name, service_desc)
                    services.add(name)
                else:
                    _LOGGER.warning(
                        "%s defined in %s has unknown decorator @%s",
                        name,
                        file,
                        dec_name,
                    )
            for dec_name in trig_decorators:
                if dec_name in trig_args and len(trig_args[dec_name]) == 0:
                    trig_args[dec_name] = None

            arg_check = {
                "state_trigger": {1},
                "state_active": {1},
                "event_trigger": {1, 2},
            }
            for dec_name, arg_cnt in arg_check.items():
                if dec_name not in trig_args or trig_args[dec_name] is None:
                    continue
                if len(trig_args[dec_name]) not in arg_cnt:
                    _LOGGER.error(
                        "%s defined in %s decorator @%s got %d argument%s, expected %s; ignored",
                        name,
                        file,
                        dec_name,
                        len(trig_args[dec_name]),
                        "s" if len(trig_args[dec_name]) > 1 else "",
                        " or ".join(sorted(arg_cnt)),
                    )
                    del trig_args[dec_name]
                if arg_cnt == 1:
                    trig_args[dec_name] = trig_args[dec_name][0]

            if len(trig_args) == 0:
                continue

            trig_args["action"] = func
            trig_args["action_ast_ctx"] = AstEval(
                name,
                global_sym_table=global_sym_table,
                state_func=state_func,
                event_func=event_func,
                handler_func=handler_func,
            )
            handler_func.install_ast_funcs(trig_args["action_ast_ctx"])
            trig_args["global_sym_table"] = global_sym_table
            triggers[name] = TrigInfo(
                name,
                trig_args,
                event_func=event_func,
                state_func=state_func,
                handler_func=handler_func,
                trig_time=trig_time_func,
            )

    return triggers, services
