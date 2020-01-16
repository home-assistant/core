#!/bin/sh -eu

# Activate pyenv and virtualenv if present, then run the specified command

# pyenv, pyenv-virtualenv
if [ -s .python-version ]; then
    PYENV_VERSION=$(head -n 1 .python-version)
    export PYENV_VERSION
fi

# other common virtualenvs
for venv in venv .venv .; do
    if [ -f $venv/bin/activate ]; then
        . $venv/bin/activate
    fi
done

exec "$@"
