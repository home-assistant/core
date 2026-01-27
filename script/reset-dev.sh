#! /bin/bash

exit_on_error () {
  echo Executing: $cmd
  echo `$cmd`
  if [ $? -eq 0 ]
  then
    return 0
  else
    echo "Failed to execute $cmd" >&2
    exit 1
  fi
}

echo "Resetting dev branch to upstream/dev and installing dependencies"

cmd="git stash -m WIP"
exit_on_error
cmd="git checkout dev"
exit_on_error
cmd="git fetch upstream"
exit_on_error
cmd="git reset --hard upstream/dev"
exit_on_error
cmd="git push"
exit_on_error
cmd="git stash pop"
exit_on_error
uv pip install -r requirements_all.txt
uv pip install -r requirements_test.txt

echo "Devcontainer reset to dev branch and dependencies installation complete!"