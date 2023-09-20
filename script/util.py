"""Util package."""
import asyncio
import os
import shlex
import sys

try:
    from colorlog.escape_codes import escape_codes
except ImportError:
    escape_codes = None

PASS = "green"
FAIL = "bold_red"


def printc(the_color, *args):
    """Color print helper."""
    msg = " ".join(args)
    if not escape_codes:
        print(msg)
        return
    try:
        print(escape_codes[the_color] + msg + escape_codes["reset"])
    except KeyError as err:
        print(msg)
        raise ValueError(f"Invalid color {the_color}") from err


async def read_stream(stream, display):
    """Read from stream line by line until EOF, display, and capture lines."""
    output = []
    while True:
        line = await stream.readline()
        if not line:
            break
        output.append(line)
        display(line.decode())  # assume it doesn't block
    return b"".join(output)


async def async_exec(*args, display=False):
    """Execute, return code & log."""
    argsp = []
    for arg in args:
        if os.path.isfile(arg):
            argsp.append(f"\\\n  {shlex.quote(arg)}")
        else:
            argsp.append(shlex.quote(arg))
    printc("cyan", *argsp)
    try:
        kwargs = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.STDOUT,
        }
        if display:
            kwargs["stderr"] = asyncio.subprocess.PIPE
        proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    except FileNotFoundError as err:
        printc(FAIL, f"Could not execute {args[0]}. Did you install test requirements?")
        raise err

    if not display:
        # Readin stdout into log
        stdout, _ = await proc.communicate()
    else:
        # read child's stdout/stderr concurrently (capture and display)
        stdout, _ = await asyncio.gather(
            read_stream(proc.stdout, sys.stdout.write),
            read_stream(proc.stderr, sys.stderr.write),
        )
    exit_code = await proc.wait()
    stdout = stdout.decode("utf-8")
    return exit_code, stdout


async def async_safe_exec(*args: str, display: bool = False) -> str:
    """Execute and raise Error, if command exit code != 0, return log."""
    exit_code, log = await async_exec(*args, display=display)
    if exit_code != 0:
        raise RuntimeError(f'Command "{args}" returned the error "{log}"')
    return log
