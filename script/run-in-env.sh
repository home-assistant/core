#!/usr/bin/env sh -eu

# Activate pyenv and virtualenv if present, then run the specified command

# pyenv, pyenv-virtualenv
if [ -s .python-version ]; then
    PYENV_VERSION=$(head -n 1 .python-version)
    export PYENV_VERSION
fi

# other common virtualenvs
my_path="."
sed_cmd=`which sed`
if [ "${sed_cmd}" == "" ]; then
	if [ -f "/usr/bin/sed" ]; then
		sed_cmd="/usr/bin/sed"
	fi
fi
if [ "${sed_cmd}" != "" ]; then
	if [ "$0" != "" ]; then
		my_path=`echo $0 | ${sed_cmd} -e 's;\/[^/]*$;;'`
		my_path="${my_path}/.."
	fi
fi

for venv in venv .venv .; do
    if [ -f ${my_path}/$venv/bin/activate ]; then
        . ${my_path}/$venv/bin/activate
    fi
done

exec "$@"
