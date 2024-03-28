#!/usr/bin/env sh
set -eu

# Used in venv activate script.
# Would be an error if undefined.
OSTYPE="${OSTYPE-}"

# Activate pyenv and virtualenv if present, then run the specified command

# pyenv, pyenv-virtualenv
if [ -s .python-version ]; then
    PYENV_VERSION=$(head -n 1 .python-version)
    export PYENV_VERSION
fi

if [ -n "${VIRTUAL_ENV}" ] && [ -f "${VIRTUAL_ENV}/bin/activate" ]; then
  . "${VIRTUAL_ENV}/bin/activate"
else
  # other common virtualenvs
  my_path=$(git rev-parse --show-toplevel)

  for venv in venv .venv .; do
    if [ -f "${my_path}/${venv}/bin/activate" ]; then
      . "${my_path}/${venv}/bin/activate"
      break
    fi
  done
fi

exec "$@"
