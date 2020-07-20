"""Function call handling."""

import asyncio
import logging
import traceback

_LOGGER = logging.getLogger(__name__)


def current_task():
    """Return our asyncio current task."""
    try:
        # python >= 3.7
        return asyncio.current_task()
    except AttributeError:
        # python <= 3.6
        return asyncio.tasks.Task.current_task()


class Handler:
    """Define function handler functions."""

    def __init__(self, hass):
        """Initialize State."""
        self.hass = hass
        self.unique_task2_name = {}
        self.unique_name2_task = {}

        #
        # initial list of available functions
        #
        self.functions = {
            "event.fire": self.event_fire,
            "task.sleep": self.async_sleep,
            "task.unique": self.task_unique,
            "service.call": self.service_call,
            "service.has_service": self.service_has_service,
        }

        #
        # Functions that take the AstEval context as a first argument,
        # which is needed by a handful of special functions that need the
        # ast context
        #

        self.ast_functions = {
            "log.debug": self.get_logger_debug,
            "log.error": self.get_logger_error,
            "log.info": self.get_logger_info,
            "log.warning": self.get_logger_warning,
        }

        #
        # We create loggers for each top-level function that include
        # that function's name.  We cache them here so we only create
        # one for each function
        #
        self.loggers = {}

    async def async_sleep(self, duration):
        """Implement task.sleep()."""
        await asyncio.sleep(float(duration))

    async def event_fire(self, event_type, **kwargs):
        """Implement event.fire()."""
        self.hass.bus.async_fire(event_type, kwargs)

    async def task_unique(self, name, kill_me=False):
        """Implement task.unique()."""
        task = current_task()
        if name in self.unique_name2_task:
            if not kill_me:
                task = self.unique_name2_task[name]
            try:
                task.cancel()
                await task
            except asyncio.CancelledError:
                pass
            self.unique_task2_name.pop(self.unique_name2_task[name], None)
            self.unique_name2_task.pop(name, None)
        self.unique_name2_task[name] = task
        self.unique_name2_task[task] = name

    def service_has_service(self, domain, name):
        """Implement service.has_service()."""
        return self.hass.services.has_service(domain, name)

    async def service_call(self, domain, name, **kwargs):
        """Implement service.call()."""
        await self.hass.services.async_call(domain, name, kwargs)

    def get_logger(self, ast_ctx, log_type, *arg, **kw):
        """Return a logger function tied to the execution context of a function."""

        if ast_ctx.name not in self.loggers:
            #
            # Maintain a cache for efficiency.  Remove last name (handlers)
            # and replace with "func.{name}".
            #
            name = __name__
            i = name.rfind(".")
            if i >= 0:
                name = f"{name[0:i]}.func.{ast_ctx.name}"
            self.loggers[ast_ctx.name] = logging.getLogger(name)
        return getattr(self.loggers[ast_ctx.name], log_type)

    def get_logger_debug(self, ast_ctx, *arg, **kw):
        """Implement log.debug()."""
        return self.get_logger(ast_ctx, "debug", *arg, **kw)

    def get_logger_error(self, ast_ctx, *arg, **kw):
        """Implement log.error()."""
        return self.get_logger(ast_ctx, "error", *arg, **kw)

    def get_logger_info(self, ast_ctx, *arg, **kw):
        """Implement log.info()."""
        return self.get_logger(ast_ctx, "info", *arg, **kw)

    def get_logger_warning(self, ast_ctx, *arg, **kw):
        """Implement log.warning()."""
        return self.get_logger(ast_ctx, "warning", *arg, **kw)

    def register(self, funcs):
        """Register functions to be available for calling."""
        for name, func in funcs.items():
            self.functions[name] = func

    def deregister(self, *names):
        """Deregister functions."""
        for name in names:
            if name in self.functions:
                del self.functions[name]

    def register_ast(self, funcs):
        """Register functions that need ast context to be available for calling."""
        for name, func in funcs.items():
            self.ast_functions[name] = func

    def deregister_ast(self, *names):
        """Deregister functions that need ast context."""
        for name in names:
            if name in self.ast_functions:
                del self.ast_functions[name]

    def install_ast_funcs(self, ast_ctx):
        """Install ast functions into the local symbol table."""
        sym_table = {}
        for name, func in self.ast_functions.items():
            sym_table[name] = func(ast_ctx)
        ast_ctx.set_local_sym_table(sym_table)

    def get(self, name):
        """Lookup a function locally and then as a service."""
        func = self.functions.get(name, None)
        if func:
            return func
        parts = name.split(".", 1)
        if len(parts) != 2:
            return None
        domain = parts[0]
        service = parts[1]
        if not self.hass.services.has_service(domain, service):
            return None

        async def service_call(*args, **kwargs):
            await self.hass.services.async_call(domain, service, kwargs)

        return service_call

    async def run_coro(self, coro):
        """Run coroutine task and update unique task on start and exit."""
        try:
            await coro
        except asyncio.CancelledError:
            task = current_task()
            if task in self.unique_task2_name:
                self.unique_name2_task.pop(self.unique_task2_name[task], None)
                self.unique_task2_name.pop(task, None)
            raise
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("run_coro: %s", traceback.format_exc(-1))
        task = current_task()
        if task in self.unique_task2_name:
            self.unique_name2_task.pop(self.unique_task2_name[task], None)
            self.unique_task2_name.pop(task, None)

    def create_task(self, coro):
        """Create a new task that runs a coroutine."""
        return self.hass.loop.create_task(self.run_coro(coro))
