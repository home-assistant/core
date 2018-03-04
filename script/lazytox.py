#!/usr/bin/env python
"""
Lazy 'tox' to quickly check if branch is up to PR standards.

This is NOT a tox replacement, only a quick check during development.
"""
import os
import asyncio
import sys
import re
from collections import namedtuple

RE_ASCII = re.compile(r"\033\[[^m]*m")
ERROR = namedtuple('ERROR', "file line col msg")


def validate_requirements_ok():
    """Validate requirements, returns True of ok."""
    # pylint: disable=E0402
    from .gen_requirements_all import main
    return main(True) == 0


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


async def async_exec(*args, mute_err=False, capture=True):
    """Execute, return code & log."""
    try:
        kwargs = {'loop': LOOP, 'stdout': asyncio.subprocess.PIPE,
                  'stderr': asyncio.subprocess.STDOUT}
        if mute_err:
            kwargs['stderr'] = asyncio.subprocess.DEVNULL
        if not capture:
            kwargs['stderr'] = asyncio.subprocess.PIPE
        # pylint: disable=E1120
        proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    except FileNotFoundError as err:
        print('ERROR: You need to install {}. Could not execute: {}'.format(
            args[0], ' '.join(args)))
        raise err

    if capture:
        # Readin stdout into log
        stdout, _ = await proc.communicate()
    else:
        # read child's stdout/stderr concurrently (capture and display)
        stdout, _ = await asyncio.gather(
            read_stream(proc.stdout, sys.stdout.write),
            read_stream(proc.stderr, sys.stderr.write))
    exit_code = await proc.wait()
    # Convert to ASCII
    stdout = stdout.decode('utf-8')
    # log = RE_ASCII.sub('', log.decode())
    return exit_code, stdout


async def git():
    """Exec git."""
    try:
        with open('lazytox.log') as file:
            oldfiles = file.readlines()
    except FileNotFoundError:
        oldfiles = []

    try:
        _, log = await async_exec(
            'git', 'diff', 'upstream/dev...', '--name-only')
    except FileNotFoundError:
        print("Using a cached version of changed files.")
        return '\n'.join(oldfiles)

    if oldfiles != log:
        with open('lazytox.log', 'w') as file:
            file.write(log)
    return log


async def pylint(files):
    """Exec pylint."""
    try:
        # Drops STDERR, it contains info on loading config file
        _, log = await async_exec('pylint', '-f', 'parseable', *files,
                                  mute_err=True)
    except FileNotFoundError:
        return []

    res = []
    for line in log.splitlines():
        line = line.split(':')
        if len(line) != 4:
            continue
        res.append(ERROR(line[0].replace('\\', '/'), line[1], "", line[2]))
    return res


async def flake8(files):
    """Exec flake8."""
    try:
        _, log = await async_exec('flake8', *files)
    except FileNotFoundError:
        return []
    res = []
    for line in log.splitlines():
        line = line.split(':')
        if len(line) != 4:
            continue
        res.append(ERROR(line[0], line[1], line[2], line[3].strip()))
    return res


async def main():
    """Main loop."""
    # Ensure we are in the homeassistant root
    os.chdir(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

    files = await git()
    if not files:
        print("No changed files found. Please ensure you have added your "
              "changes with git add & git commit")
        return

    files = files.splitlines()
    pyfile = re.compile(r".+\.py$")
    pyfiles = [file for file in files if pyfile.match(file)]

    print("CHANGED FILES:", ' '.join(files))
    print("============================")

    fres, pres = await asyncio.gather(flake8(pyfiles), pylint(pyfiles))
    res = fres + pres

    res.sort(key=lambda item: item.file)

    gen_req = False
    lint_ok = True
    test_files = set()

    for err in res:
        print("{} {}:{} {}".format(err.file, err.line, err.col, err.msg))

        # Will run generate_requirements if components and lint passes
        if err.file.startswith('homeassistant/components/'):
            gen_req = True

        # Ignore tests/ for the lint_ok test, but otherwise we have an issue
        if not err.file.startswith('tests/'):
            lint_ok = False

        # Try find test files...
        if err.file.startswith('tests/'):
            test_files.add(err.file)
        else:
            tfile = err.file.replace('homeassistant', 'tests') \
                .replace('__init__', 'test_init')
            if tfile.startswith('tests') and os.path.isfile(tfile):
                test_files.add(tfile)

    if not lint_ok:
        print('Please fix your lint issues before continuing')
        return

    if gen_req:
        print("============================")
        if validate_requirements_ok():
            print("script/gen_requirements.py passed")
        else:
            print("Please run script/gen_requirements.py before submitting")
            return

    print("============================")
    print('pytest -vv --', ' '.join(test_files))
    print("============================")
    if not test_files:
        print("No files identified, running pytest on everything.")
    code, _ = await async_exec(
        'pytest', '-vv', '--', *test_files, capture=False)
    print("============================")

    if code == 0:
        print("Yay! This will most likely pass tox")
    else:
        print("Test not passing")


if __name__ == '__main__':
    LOOP = asyncio.ProactorEventLoop() if sys.platform == 'win32' \
        else asyncio.get_event_loop()

    try:
        LOOP.run_until_complete(main())
    except KeyboardInterrupt:
        exit
    finally:
        LOOP.close()
