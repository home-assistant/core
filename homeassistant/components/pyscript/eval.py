"""Python interpreter for pyscript."""

import ast
import asyncio
import importlib
import logging
import sys
import traceback

_LOGGER = logging.getLogger(__name__)

#
# Built-in functions available.  Certain functions are excluded
# to avoid potential security issues.
#
BUILTIN_FUNCS = {
    "abs": abs,
    "all": all,
    "any": any,
    "ascii": ascii,
    "bin": bin,
    "bool": bool,
    "bytearray": bytearray,
    "bytearray.fromhex": bytearray.fromhex,
    "bytes": bytes,
    "bytes.fromhex": bytes.fromhex,
    "callable": callable,
    "chr": chr,
    "complex": complex,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "hash": hash,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
}


ALLOWED_IMPORTS = {
    "cmath",
    "datetime",
    "decimal",
    "fractions",
    "homeassistant.const",
    "math",
    "number",
    "random",
    "re",
    "statistics",
    "string",
    "time",
}


#
# Objects returned by return, break and continue statements that change execution flow
#
class EvalStopFlow:
    """Denotes a statement or action that stops execution flow, eg: return, break etc."""


class EvalReturn(EvalStopFlow):
    """Return statement."""

    def __init__(self, value):
        """Initialize return statement value."""
        self.value = value


class EvalBreak(EvalStopFlow):
    """Break statement."""


class EvalContinue(EvalStopFlow):
    """Continue statement."""


class EvalName:
    """Identifier that hasn't yet been resolved."""

    def __init__(self, name):
        """Initialize identifier to name."""
        self.name = name


class EvalFunc:
    """Class for a callable pyscript function."""

    def __init__(self, func_def):
        """Initialize a function calling context."""
        self.func_def = func_def
        self.name = func_def.name
        self.defaults = []
        self.kw_defaults = []
        self.decorators = []
        self.global_names = set()
        self.nonlocal_names = set()
        self.doc_string = ast.get_docstring(func_def)
        self.num_posn_arg = len(self.func_def.args.args) - len(self.defaults)

    def get_name(self):
        """Return the function name."""
        return self.name

    async def eval_defaults(self, ast_ctx):
        """Evaluate the default function arguments."""
        self.defaults = []
        for val in self.func_def.args.defaults:
            self.defaults.append(await ast_ctx.aeval(val))
        self.num_posn_arg = len(self.func_def.args.args) - len(self.defaults)
        self.kw_defaults = []
        for val in self.func_def.args.kw_defaults:
            self.kw_defaults.append(
                {"ok": bool(val), "val": None if not val else await ast_ctx.aeval(val)}
            )

    async def eval_decorators(self, ast_ctx):
        """Evaluate the function decorators arguments."""
        self.decorators = []
        for dec in self.func_def.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                args = []
                for arg in dec.args:
                    args.append(await ast_ctx.aeval(arg))
                self.decorators.append([dec.func.id, args])
            elif isinstance(dec, ast.Name):
                self.decorators.append([dec.id, None])
            else:
                _LOGGER.error(
                    "function %s has unexpected decorator type %s", self.name, dec
                )

    def get_decorators(self):
        """Return the function decorators."""
        return self.decorators

    def get_doc_string(self):
        """Return the function doc_string."""
        return self.doc_string

    def get_positional_args(self):
        """Return the function positional arguments."""
        args = []
        for arg in self.func_def.args.args:
            args.append(arg.arg)
        return args

    async def call(self, ast_ctx, args=None, kwargs=None):
        """Call the function with the given context and arguments."""
        sym_table = {}
        if args is None:
            args = []
        kwargs = kwargs.copy() if kwargs else {}
        for i in range(len(self.func_def.args.args)):
            var_name = self.func_def.args.args[i].arg
            val = None
            if i < len(args):
                val = args[i]
                if var_name in kwargs:
                    raise TypeError(
                        "{self.name}() got multiple values for argument '{var_name}'"
                    )
            elif var_name in kwargs:
                val = kwargs[var_name]
                del kwargs[var_name]
            elif self.num_posn_arg <= i < len(self.defaults) + self.num_posn_arg:
                val = self.defaults[i - self.num_posn_arg]
            else:
                raise TypeError(
                    f"{self.name}() missing {self.num_posn_arg - i} required positional arguments"
                )
            sym_table[var_name] = val
        for i in range(len(self.func_def.args.kwonlyargs)):
            var_name = self.func_def.args.kwonlyargs[i].arg
            if var_name in kwargs:
                val = kwargs[var_name]
                del kwargs[var_name]
            elif i < len(self.kw_defaults) and self.kw_defaults[i]["ok"]:
                val = self.kw_defaults[i]["val"]
            else:
                raise TypeError(
                    f"{self.name}() missing required keyword-only arguments"
                )
            sym_table[var_name] = val
        if self.func_def.args.kwarg:
            sym_table[self.func_def.args.kwarg.arg] = kwargs
        if self.func_def.args.vararg:
            if len(args) > len(self.func_def.args.args):
                sym_table[self.func_def.args.vararg.arg] = tuple(
                    args[len(self.func_def.args.args) :]
                )
            else:
                sym_table[self.func_def.args.vararg.arg] = ()
        elif len(args) > len(self.func_def.args.args):
            raise TypeError(f"{self.name}() called with too many positional arguments")
        ast_ctx.sym_table_stack.append(ast_ctx.sym_table)
        ast_ctx.sym_table = sym_table
        prev_func = ast_ctx.curr_func
        ast_ctx.curr_func = self
        for arg1 in self.func_def.body:
            val = await ast_ctx.aeval(arg1)
            if isinstance(val, EvalReturn):
                val = val.value
                break
            # return None at end if there isn't a return
            val = None
        ast_ctx.sym_table = ast_ctx.sym_table_stack.pop()
        ast_ctx.curr_func = prev_func
        return val


class AstEval:
    """Python interpreter AST object evaluator."""

    def __init__(
        self,
        name,
        global_sym_table=None,
        state_func=None,
        event_func=None,
        handler_func=None,
    ):
        """Initialize a interpreter execution context."""
        self.name = name
        self.str = None
        self.ast = None
        self.global_sym_table = global_sym_table if global_sym_table is not None else {}
        self.sym_table_stack = []
        self.sym_table = self.global_sym_table
        self.local_sym_table = {}
        self.curr_func = None
        self.filename = ""
        self.exception = None
        self.exception_long = None
        self.state = state_func
        self.handler = handler_func
        self.event = event_func

    async def ast_not_implemented(self, arg, *args):
        """Raise NotImplementedError exception for unimplemented AST types."""
        name = "ast_" + arg.__class__.__name__.lower()
        raise NotImplementedError(f"{self.name}: not implemented ast " + name)

    async def aeval(self, arg, undefined_check=True):
        """Vector to specific function based on ast class type."""
        name = "ast_" + arg.__class__.__name__.lower()
        try:
            func = getattr(self, name, self.ast_not_implemented)
            if asyncio.iscoroutinefunction(func):
                val = await func(arg)
            else:
                val = func(arg)
            if undefined_check and isinstance(val, EvalName):
                raise NameError(f"name '{val.name}' is not defined")
            return val
        except asyncio.CancelledError:  # pylint: disable=try-except-raise
            raise
        except Exception as err:  # pylint: disable=broad-except
            func_name = self.curr_func.get_name() + "(), " if self.curr_func else ""
            self.exception = f"Exception in {func_name}{self.filename} line {arg.lineno} column {arg.col_offset}: {err}"
            self.exception_long = f"Exception in {func_name}{self.filename} line {arg.lineno} column {arg.col_offset}: {traceback.format_exc(0)}"
            _LOGGER.error(
                "Exception in %s%s line %s column %s: %s",
                func_name,
                self.filename,
                arg.lineno,
                arg.col_offset,
                err,
            )
        return None

    # Statements return NONE, EvalBreak, EvalContinue, EvalReturn
    async def ast_module(self, arg):
        """Execute ast_module - a list of statements."""
        val = None
        for arg1 in arg.body:
            val = await self.aeval(arg1)
            if isinstance(val, EvalStopFlow):
                return val
        return val

    async def ast_import(self, arg):
        """Execute import."""
        for imp in arg.names:
            if imp.name not in ALLOWED_IMPORTS:
                raise ModuleNotFoundError(f"import of {imp.name} not allowed")
            if imp.name not in sys.modules:
                mod = importlib.import_module(imp.name)
            else:
                mod = sys.modules[imp.name]
            self.sym_table[imp.name if imp.asname is None else imp.asname] = mod

    async def ast_importfrom(self, arg):
        """Execute from X import Y."""
        if arg.module not in ALLOWED_IMPORTS:
            raise ModuleNotFoundError(f"import from {arg.module} not allowed")
        if arg.module not in sys.modules:
            mod = importlib.import_module(arg.module)
        else:
            mod = sys.modules[arg.module]
        for imp in arg.names:
            self.sym_table[imp.name if imp.asname is None else imp.asname] = getattr(
                mod, imp.name
            )

    async def ast_if(self, arg):
        """Execute if statement."""
        val = None
        if await self.aeval(arg.test):
            for arg1 in arg.body:
                val = await self.aeval(arg1)
                if isinstance(val, EvalStopFlow):
                    return val
        else:
            for arg1 in arg.orelse:
                val = await self.aeval(arg1)
                if isinstance(val, EvalStopFlow):
                    return val
        return val

    async def ast_for(self, arg):
        """Execute for statement."""
        loop_var = await self.aeval(arg.target)
        loop_iter = await self.aeval(arg.iter)
        for i in loop_iter:
            self.sym_table[loop_var] = i
            for arg1 in arg.body:
                val = await self.aeval(arg1)
                if isinstance(val, EvalStopFlow):
                    break
            if isinstance(val, EvalBreak):
                break
            if isinstance(val, EvalContinue):
                continue
            if isinstance(val, EvalReturn):
                return val
        if not isinstance(val, EvalBreak):
            for arg1 in arg.orelse:
                val = await self.aeval(arg1)
                if isinstance(val, EvalReturn):
                    return val
        return None

    async def ast_while(self, arg):
        """Execute while statement."""
        while 1:
            val = await self.aeval(arg.test)
            if not val:
                break
            for arg1 in arg.body:
                val = await self.aeval(arg1)
                if isinstance(val, EvalStopFlow):
                    break
            if isinstance(val, EvalBreak):
                break
            if isinstance(val, EvalContinue):
                continue
            if isinstance(val, EvalReturn):
                return val
        if not isinstance(val, EvalBreak):
            for arg1 in arg.orelse:
                val = await self.aeval(arg1)
                if isinstance(val, EvalReturn):
                    return val
        return None

    async def ast_pass(self, arg):
        """Execute pass statement."""

    async def ast_expr(self, arg):
        """Execute expression statement."""
        return await self.aeval(arg.value)

    async def ast_break(self, arg):
        """Execute break statement - return special class."""
        return EvalBreak()

    async def ast_continue(self, arg):
        """Execute continue statement - return special class."""
        return EvalContinue()

    async def ast_return(self, arg):
        """Execute return statement - return special class."""
        val = await self.aeval(arg.value)
        return EvalReturn(val)

    async def ast_global(self, arg):
        """Execute global statement."""
        if self.curr_func:
            for var_name in arg.names:
                self.curr_func.global_names.add(var_name)

    async def ast_nonlocal(self, arg):
        """Execute nonlocal statement."""
        if self.curr_func:
            for var_name in arg.names:
                self.curr_func.nonlocal_names.add(var_name)

    async def ast_assign(self, arg):
        """Execute assignment statement."""
        val = await self.aeval(arg.value)
        for lhs in arg.targets:  # pylint: disable=too-many-nested-blocks
            if isinstance(lhs, ast.Subscript):
                var = await self.aeval(lhs.value)
                if isinstance(lhs.slice, ast.Index):
                    ind = await self.aeval(lhs.slice.value)
                    var[ind] = val
                elif isinstance(lhs.slice, ast.Slice):
                    lower = (
                        await self.aeval(lhs.slice.lower) if lhs.slice.lower else None
                    )
                    upper = (
                        await self.aeval(lhs.slice.upper) if lhs.slice.upper else None
                    )
                    step = await self.aeval(lhs.slice.step) if lhs.slice.step else None
                    if not lower and not upper and not step:
                        return val
                    if not lower and not upper and step:
                        var[::step] = val
                    elif not lower and upper and not step:
                        var[:upper] = val
                    elif not lower and upper and step:
                        var[:upper:step] = val
                    elif lower and not upper and not step:
                        var[lower] = val
                    elif lower and not upper and step:
                        var[lower::step] = val
                    elif lower and upper and not step:
                        var[lower:upper] = val
                    else:
                        var[lower:upper:step] = val
            else:
                var_name = await self.aeval(lhs)
                if var_name.find(".") >= 0:
                    self.state.set(var_name, val)
                else:
                    if self.curr_func and var_name in self.curr_func.global_names:
                        self.global_sym_table[var_name] = val
                    elif self.curr_func and var_name in self.curr_func.nonlocal_names:
                        for sym_table in reversed(self.sym_table_stack):
                            if var_name in sym_table:
                                sym_table[var_name] = val
                                break
                        else:
                            raise TypeError(
                                "can't find nonlocal '{var_name}' for assignment"
                            )
                    else:
                        self.sym_table[var_name] = val

    async def ast_augassign(self, arg):
        """Execute augmented assignment statement (lhs <BinOp>= value)."""
        var_name = await self.aeval(arg.target)
        val = await self.aeval(
            ast.BinOp(
                left=ast.Name(id=var_name, ctx=ast.Load()), op=arg.op, right=arg.value
            )
        )
        if self.curr_func and var_name in self.curr_func.global_names:
            self.global_sym_table[var_name] = val
        elif self.curr_func and var_name in self.curr_func.nonlocal_names:
            for sym_table in reversed(self.sym_table_stack):
                if var_name in sym_table:
                    sym_table[var_name] = val
                    break
            else:
                raise TypeError("can't find nonlocal '{var_name}' for assignment")
        else:
            self.sym_table[var_name] = val

    async def ast_delete(self, arg):
        """Execute del statement."""
        for arg1 in arg.targets:
            if isinstance(arg1, ast.Subscript):
                var = await self.aeval(arg1.value)
                if isinstance(arg1.slice, ast.Index):
                    ind = await self.aeval(arg1.slice.value)
                    for elt in ind if isinstance(ind, list) else [ind]:
                        del var[elt]
                else:
                    raise NotImplementedError(
                        f"{self.name}: not implemented slice type {arg1.slice} in del"
                    )
            elif isinstance(arg1, ast.Name):
                if self.curr_func and arg1.id in self.curr_func.global_names:
                    if arg1.id in self.global_sym_table:
                        del self.global_sym_table[arg1.id]
                elif self.curr_func and arg1.id in self.curr_func.nonlocal_names:
                    for sym_table in reversed(self.sym_table_stack):
                        if arg1.id in sym_table:
                            del sym_table[arg1.id]
                            break
                elif arg1.id in self.sym_table:
                    del self.sym_table[arg1.id]
                else:
                    raise NameError(f"name '{arg1.id}' is not defined in del")
            else:
                raise NotImplementedError(f"unknown target type {arg1} in del")

    def ast_attribute2_name(self, arg):  # pylint: disable=no-self-use
        """Combine dotted attributes to allow variable names to have dots."""
        # collapse dotted names, eg:
        #   Attribute(value=Attribute(value=Name(id='i', ctx=Load()), attr='j', ctx=Load()), attr='k', ctx=Store())
        name = arg.attr
        val = arg.value
        while isinstance(val, ast.Attribute):
            name = val.attr + "." + name
            val = val.value
        if isinstance(val, ast.Name):
            name = val.id + "." + name
        else:
            return None
        return name

    async def ast_attribute(self, arg):
        """Assemble or apply attributes."""
        full_name = self.ast_attribute2_name(arg)
        if full_name is not None:
            val = await self.ast_name(ast.Name(id=full_name, ctx=arg.ctx))
        else:
            val = await self.aeval(arg.value, undefined_check=False)
            if isinstance(val, EvalName):
                return await self.ast_name(
                    ast.Name(id=f"{val.name}.{arg.attr}", ctx=arg.ctx)
                )
            return getattr(val, arg.attr, None)
        if isinstance(val, EvalName):
            parts = full_name.rsplit(".", 1)
            if len(parts) == 2:
                val = await self.ast_name(ast.Name(id=parts[0], ctx=arg.ctx))
                val = getattr(val, parts[1])
        return val

    async def ast_name(self, arg):
        """Look up value of identifier on load, or returns name on set."""
        if isinstance(arg.ctx, ast.Load):
            #
            # check other scopes if required by global or nonlocal declarations
            #
            if self.curr_func and arg.id in self.curr_func.global_names:
                if arg.id in self.global_sym_table:
                    return self.global_sym_table[arg.id]
                raise NameError(f"global name '{arg.id}' is not defined")
            if self.curr_func and arg.id in self.curr_func.nonlocal_names:
                for sym_table in reversed(self.sym_table_stack):
                    if arg.id in sym_table:
                        return sym_table[arg.id]
                raise NameError(f"nonlocal name '{arg.id}' is not defined")
            #
            # now check in our current symbol table, and then some other places
            #
            if arg.id in self.sym_table:
                return self.sym_table[arg.id]
            if arg.id in self.local_sym_table:
                return self.local_sym_table[arg.id]
            if arg.id in self.global_sym_table:
                return self.global_sym_table[arg.id]
            if arg.id in BUILTIN_FUNCS:
                return BUILTIN_FUNCS[arg.id]
            if self.handler.get(arg.id):
                return self.handler.get(arg.id)
            if self.state.exist(arg.id):
                return self.state.get(arg.id)
            #
            # Couldn't find it, so return just the name wrapped in EvalName to
            # distinguish from a string variable value.  This is to support
            # names with ".", which are joined by ast_attribute
            #
            return EvalName(arg.id)
        return arg.id

    async def ast_binop(self, arg):
        """Evaluate binary operators by calling function based on class."""
        name = "ast_binop_" + arg.op.__class__.__name__.lower()
        return await getattr(self, name, self.ast_not_implemented)(arg.left, arg.right)

    async def ast_binop_add(self, arg0, arg1):
        """Evaluate binary operator: +."""
        return (await self.aeval(arg0)) + (await self.aeval(arg1))

    async def ast_binop_sub(self, arg0, arg1):
        """Evaluate binary operator: -."""
        return (await self.aeval(arg0)) - (await self.aeval(arg1))

    async def ast_binop_mult(self, arg0, arg1):
        """Evaluate binary operator: *."""
        return (await self.aeval(arg0)) * (await self.aeval(arg1))

    async def ast_binop_div(self, arg0, arg1):
        """Evaluate binary operator: /."""
        return (await self.aeval(arg0)) / (await self.aeval(arg1))

    async def ast_binop_mod(self, arg0, arg1):
        """Evaluate binary operator: %."""
        return (await self.aeval(arg0)) % (await self.aeval(arg1))

    async def ast_binop_pow(self, arg0, arg1):
        """Evaluate binary operator: **."""
        return (await self.aeval(arg0)) ** (await self.aeval(arg1))

    async def ast_binop_lshift(self, arg0, arg1):
        """Evaluate binary operator: <<."""
        return (await self.aeval(arg0)) << (await self.aeval(arg1))

    async def ast_binop_rshift(self, arg0, arg1):
        """Evaluate binary operator: >>."""
        return (await self.aeval(arg0)) >> (await self.aeval(arg1))

    async def ast_binop_bitor(self, arg0, arg1):
        """Evaluate binary operator: |."""
        return (await self.aeval(arg0)) | (await self.aeval(arg1))

    async def ast_binop_bitxor(self, arg0, arg1):
        """Evaluate binary operator: ^."""
        return (await self.aeval(arg0)) ^ (await self.aeval(arg1))

    async def ast_binop_bitand(self, arg0, arg1):
        """Evaluate binary operator: &."""
        return (await self.aeval(arg0)) & (await self.aeval(arg1))

    async def ast_binop_floordiv(self, arg0, arg1):
        """Evaluate binary operator: //."""
        return (await self.aeval(arg0)) // (await self.aeval(arg1))

    async def ast_unaryop(self, arg):
        """Evaluate unary operators by calling function based on class."""
        name = "ast_unaryop_" + arg.op.__class__.__name__.lower()
        return await getattr(self, name, self.ast_not_implemented)(arg.operand)

    async def ast_unaryop_not(self, arg0):
        """Evaluate unary operator: not."""
        return not (await self.aeval(arg0))

    async def ast_unaryop_invert(self, arg0):
        """Evaluate unary operator: ~."""
        return ~(await self.aeval(arg0))

    async def ast_unaryop_uadd(self, arg0):
        """Evaluate unary operator: +."""
        return await self.aeval(arg0)

    async def ast_unaryop_usub(self, arg0):
        """Evaluate unary operator: -."""
        return -(await self.aeval(arg0))

    async def ast_compare(self, arg):
        """Evaluate comparison operators by calling function based on class."""
        left = arg.left
        for cmp_op, right in zip(arg.ops, arg.comparators):
            name = "ast_cmpop_" + cmp_op.__class__.__name__.lower()
            val = await getattr(self, name, self.ast_not_implemented)(left, right)
            if not val:
                return False
            left = right
        return True

    async def ast_cmpop_eq(self, arg0, arg1):
        """Evaluate comparison operator: ==."""
        return (await self.aeval(arg0)) == (await self.aeval(arg1))

    async def ast_cmpop_noteq(self, arg0, arg1):
        """Evaluate comparison operator: !=."""
        return (await self.aeval(arg0)) != (await self.aeval(arg1))

    async def ast_cmpop_lt(self, arg0, arg1):
        """Evaluate comparison operator: <."""
        return (await self.aeval(arg0)) < (await self.aeval(arg1))

    async def ast_cmpop_lte(self, arg0, arg1):
        """Evaluate comparison operator: <=."""
        return (await self.aeval(arg0)) <= (await self.aeval(arg1))

    async def ast_cmpop_gt(self, arg0, arg1):
        """Evaluate comparison operator: >."""
        return (await self.aeval(arg0)) > (await self.aeval(arg1))

    async def ast_cmpop_gte(self, arg0, arg1):
        """Evaluate comparison operator: >=."""
        return (await self.aeval(arg0)) >= (await self.aeval(arg1))

    async def ast_cmpop_is(self, arg0, arg1):
        """Evaluate comparison operator: is."""
        return (await self.aeval(arg0)) is (await self.aeval(arg1))

    async def ast_cmpop_isnot(self, arg0, arg1):
        """Evaluate comparison operator: is not."""
        return (await self.aeval(arg0)) is not (await self.aeval(arg1))

    async def ast_cmpop_in(self, arg0, arg1):
        """Evaluate comparison operator: in."""
        return (await self.aeval(arg0)) in (await self.aeval(arg1))

    async def ast_cmpop_notin(self, arg0, arg1):
        """Evaluate comparison operator: not in."""
        return (await self.aeval(arg0)) not in (await self.aeval(arg1))

    async def ast_boolop(self, arg):
        """Evaluate boolean operators and and or."""
        if isinstance(arg.op, ast.And):
            val = 1
            for arg1 in arg.values:
                this_val = await self.aeval(arg1)
                if this_val == 0:
                    return 0
                val = this_val
            return val
        for arg1 in arg.values:
            val = await self.aeval(arg1)
            if val != 0:
                return val
        return 0

    async def eval_elt_list(self, elts):
        """Evaluate and star list elements."""
        val = []
        for arg in elts:
            if isinstance(arg, ast.Starred):
                for this_val in await self.aeval(arg.value):
                    val.append(this_val)
            else:
                this_val = await self.aeval(arg)
                val.append(this_val)
        return val

    async def ast_list(self, arg):
        """Evaluate list."""
        if isinstance(arg.ctx, ast.Load):
            return await self.eval_elt_list(arg.elts)

    async def ast_tuple(self, arg):
        """Evaluate Tuple."""
        if isinstance(arg.ctx, ast.Load):
            return tuple(await self.eval_elt_list(arg.elts))

    async def ast_dict(self, arg):
        """Evaluate dict."""
        val = {}
        for key_ast, val_ast in zip(arg.keys, arg.values):
            this_val = await self.aeval(val_ast)
            if key_ast is None:
                val.update(this_val)
            else:
                val[await self.aeval(key_ast)] = this_val
        return val

    async def ast_set(self, arg):
        """Evaluate set."""
        val = set()
        for elt in await self.eval_elt_list(arg.elts):
            val.add(elt)
        return val

    async def ast_subscript(self, arg):
        """Evaluate subscript."""
        var = await self.aeval(arg.value)
        if isinstance(arg.ctx, ast.Load):
            if isinstance(arg.slice, ast.Index):
                return var[await self.aeval(arg.slice)]
            if isinstance(arg.slice, ast.Slice):
                lower = (await self.aeval(arg.slice.lower)) if arg.slice.lower else None
                upper = (await self.aeval(arg.slice.upper)) if arg.slice.upper else None
                step = (await self.aeval(arg.slice.step)) if arg.slice.step else None
                if not lower and not upper and not step:
                    return None
                if not lower and not upper and step:
                    return var[::step]
                if not lower and upper and not step:
                    return var[:upper]
                if not lower and upper and step:
                    return var[:upper:step]
                if lower and not upper and not step:
                    return var[lower]
                if lower and not upper and step:
                    return var[lower::step]
                if lower and upper and not step:
                    return var[lower:upper]
                return var[lower:upper:step]
        else:
            return None

    async def ast_index(self, arg):
        """Evaluate index."""
        return await self.aeval(arg.value)

    async def ast_slice(self, arg):
        """Evaluate slice."""
        return await self.aeval(arg.value)

    async def ast_call(self, arg):
        """Evaluate function call."""
        func = await self.aeval(arg.func)
        kwargs = {}
        for kw_arg in arg.keywords:
            if kw_arg.arg is None:
                kwargs.update(await self.aeval(kw_arg.value))
            else:
                kwargs[kw_arg.arg] = await self.aeval(kw_arg.value)
        args = await self.eval_elt_list(arg.args)
        arg_str = ", ".join(
            ['"' + elt + '"' if isinstance(elt, str) else str(elt) for elt in args]
        )

        if isinstance(func, EvalFunc):
            return await func.call(self, args, kwargs)
        #
        # try to deduce function name, although this only works in simple cases
        #
        if isinstance(arg.func, ast.Name):
            func_name = arg.func.id
        elif isinstance(arg.func, ast.Attribute):
            func_name = arg.func.attr
        else:
            func_name = "<other>"
        if callable(func):
            _LOGGER.debug(
                "%s: calling %s(%s, %s)", self.name, func_name, arg_str, kwargs
            )
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)
        raise NameError(f"function '{func_name}' is not callable (got {func})")

    async def ast_functiondef(self, arg):
        """Evaluate function definition."""
        func = EvalFunc(arg)
        await func.eval_defaults(self)
        await func.eval_decorators(self)
        self.sym_table[func.get_name()] = func
        return None

    async def ast_ifexp(self, arg):
        """Evaluate if expression."""
        return (
            await self.aeval(arg.body)
            if (await self.aeval(arg.test))
            else await self.aeval(arg.orelse)
        )

    async def ast_num(self, arg):
        """Evaluate number."""
        return arg.n

    async def ast_str(self, arg):
        """Evaluate string."""
        return arg.s

    async def ast_nameconstant(self, arg):
        """Evaluate name constant."""
        return arg.value

    async def ast_constant(self, arg):
        """Evaluate constant."""
        return arg.value

    async def ast_joinedstr(self, arg):
        """Evaluate joined string."""
        val = ""
        for arg1 in arg.values:
            this_val = await self.aeval(arg1)
            val = val + str(this_val)
        return val

    async def ast_formattedvalue(self, arg):
        """Evaluate formatted value."""
        val = await self.aeval(arg.value)
        if arg.format_spec is not None:
            fmt = await self.aeval(arg.format_spec)
            return f"{val:{fmt}}"
        return f"{val}"

    def ast_get_names2_dict(self, arg, names):
        """Recursively find all the names mentioned in the AST tree."""
        if isinstance(arg, ast.Attribute):
            names[self.ast_attribute2_name(arg)] = 1
        elif isinstance(arg, ast.Name):
            names[arg.id] = 1
        else:
            for child in ast.iter_child_nodes(arg):
                self.ast_get_names2_dict(child, names)

    def ast_get_names(self):
        """Return list of all the names mentioned in our AST tree."""
        names = {}
        if self.ast:
            self.ast_get_names2_dict(self.ast, names)
        return [*names]

    def parse(self, code_str, filename="<unknown>"):
        """Parse the code_str source code into an AST tree."""
        self.ast = None
        self.filename = filename
        try:
            if isinstance(code_str, list):
                code_str = "\n".join(code_str)
            self.str = code_str
            self.ast = ast.parse(code_str, filename=self.filename)
            return True
        except SyntaxError as err:
            self.exception = f"syntax error {err}"
            self.exception_long = traceback.format_exc(0)
            _LOGGER.error(
                "syntax error file %s: %s", self.filename, traceback.format_exc(0)
            )
            return False
        except asyncio.CancelledError:  # pylint: disable=try-except-raise
            raise
        except Exception as err:  # pylint: disable=broad-except
            self.exception = f"parsing error {err}"
            self.exception_long = traceback.format_exc(0)
            _LOGGER.error(
                "parsing error file %s: %s", self.filename, traceback.format_exc(0)
            )
            return False

    def get_exception(self):
        """Return the last exception."""
        return self.exception

    def get_exception_long(self):
        """Return the last exception in a longer form."""
        return self.exception_long

    def set_local_sym_table(self, sym_table):
        """Set the local symbol table."""
        self.local_sym_table = sym_table

    async def eval(self, new_state_vars=None):
        """Execute parsed code, with the optional state variables added to the scope."""
        self.exception = None
        self.exception_long = None
        if new_state_vars:
            self.local_sym_table.update(new_state_vars)
        if self.ast:
            val = await self.aeval(self.ast)
            if isinstance(val, EvalStopFlow):
                return None
            return val
        return None

    def dump(self):
        """Dump the AST tree for debugging."""
        return ast.dump(self.ast)
