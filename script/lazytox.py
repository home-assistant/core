#!/usr/bin/env python
"""
Lazy 'tox' to quickly check if branch is up to PR standards.

This is NOT a tox replacement, only a quick check during development.
"""
import os
import asyncio
import sys
import re
import shlex
from collections import namedtuple

RE_ASCII = re.compile(r"\033\[[^m]*m")
Error = namedtuple('ERROR',
                   "file line col msg")  # pylint: disable=invalid-name


def validate_requirements_ok():
    """Validate requirements, returns True of ok."""
    # pylint: disable=E0402
    from gen_requirements_all import main as req_main
    return req_main(True) == 0


async def read_stream(stream, display):
    """Read from stream line by line until EOF, display, and capture lines."""
    output = []
    while True:
        line = await stream.readline()
        if not line:
            break
        output.append(line)
        display(line.decode())  # assume it doesn't block
    return b''.join(output)


async def async_exec(*args, display=False):
    """Execute, return code & log."""
    try:
        kwargs = {'loop': LOOP, 'stdout': asyncio.subprocess.PIPE,
                  'stderr': asyncio.subprocess.STDOUT}
        if display:
            kwargs['stderr'] = asyncio.subprocess.PIPE
        # pylint: disable=E1120
        proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    except FileNotFoundError as err:
        print('ERROR: You need to install {}. Could not execute: {}'.format(
            args[0], ' '.join(shlex.quote(arg) for arg in args)))
        raise err

    if not display:
        # Readin stdout into log
        stdout, _ = await proc.communicate()
    else:
        # read child's stdout/stderr concurrently (capture and display)
        stdout, _ = await asyncio.gather(
            read_stream(proc.stdout, sys.stdout.write),
            read_stream(proc.stderr, sys.stderr.write))
    exit_code = await proc.wait()
    stdout = stdout.decode('utf-8')
    return exit_code, stdout


async def git():
    """Exec git."""
    if len(sys.argv) > 2 and sys.argv[1] == '--':
        return sys.argv[2:]
    _, log = await async_exec('git', 'diff', 'upstream/dev...', '--name-only')
    return log.splitlines()


async def pylint(files):
    """Exec pylint."""
    _, log = await async_exec('pylint', '-f', 'parseable', '--persistent=n',
                              *files)
    res = []
    for line in log.splitlines():
        line = line.split(':')
        if len(line) < 3:
            continue
        res.append(Error(line[0].replace('\\', '/'),
                         line[1], "", line[2].strip()))
    return res


async def flake8(files):
    """Exec flake8."""
    _, log = await async_exec('flake8', *files)
    res = []
    for line in log.splitlines():
        line = line.split(':')
        if len(line) < 4:
            continue
        res.append(Error(line[0].replace('\\', '/'),
                         line[1], line[2], line[3].strip()))
    return res


async def lint(files):
    """Perform lint."""
    fres, pres = await asyncio.gather(flake8(files), pylint(files))

    res = fres + pres
    res.sort(key=lambda item: item.file)
    if res:
        print("Pylint & Flake8 errors:")
    else:
        print("Pylint and Flake8 passed")

    lint_ok = True
    for err in res:
        print("{} {}:{} {}".format(err.file, err.line, err.col, err.msg))
        # Ignore tests/ for the lint_ok test, but otherwise we have an issue
        if not err.file.startswith('tests/'):
            lint_ok = False

    return lint_ok


async def main():
    """The main loop."""
    # Ensure we are in the homeassistant root
    os.chdir(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

    files = await git()
    if not files:
        print("No changed files found. Please ensure you have added your "
              "changes with git add & git commit")
        return

    pyfile = re.compile(r".+\.py$")
    pyfiles = [file for file in files if pyfile.match(file)]

    print("=============================")
    print("CHANGED FILES:\n", '\n '.join(pyfiles))
    print("=============================")

    skip_lint = len(sys.argv) > 1 and sys.argv[1] == '--skiplint'
    if skip_lint:
        print("WARNING: LINT DISABLED")
    elif not await lint(pyfiles):
        print('Please fix your lint issues before continuing')
        return

    test_files = set()
    gen_req = False
    for fname in pyfiles:
        if fname.startswith('homeassistant/components/'):
            gen_req = True  # requirements script for components
        # Find test files...
        if fname.startswith('tests/'):
            test_files.add(fname)
        else:
            parts = fname.split('/')
            parts[0] = 'tests'
            if parts[-1] == '__init__.py':
                parts[-1] = 'test_init.py'
            elif parts[-1] == '__main__.py':
                parts[-1] = 'test_main.py'
            else:
                parts[-1] = 'test_' + parts[-1]
            fname = '/'.join(parts)
            if os.path.isfile(fname):
                test_files.add(fname)

    if gen_req:
        print("=============================")
        if validate_requirements_ok():
            print("script/gen_requirements.py passed")
        else:
            print("Please run script/gen_requirements.py before submitting")
            return

    print("=============================")
    if not test_files:
        print("No files identified, ideally you should run tox.")
        return

    print('pytest -vv --', ' '.join(shlex.quote(fle) for fle in test_files))
    code, _ = await async_exec(
        'pytest', '-vv', '--force-sugar', '--', *test_files, display=True)
    print("\n=============================")

    if code == 0:
        print("Yay! This will most likely pass tox")
    else:
        print("Test not passing")

    if skip_lint:
        print("WARNING: LINT DISABLED")


if __name__ == '__main__':
    LOOP = asyncio.ProactorEventLoop() if sys.platform == 'win32' \
        else asyncio.get_event_loop()

    try:
        LOOP.run_until_complete(main())
    except (FileNotFoundError, KeyboardInterrupt):
        pass
    finally:
        LOOP.close()
