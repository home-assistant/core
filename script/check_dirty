#!/bin/bash
[[ -z $(git ls-files --others --exclude-standard) ]] && exit 0

echo -e '\n***** ERROR\nTests are leaving files behind. Please update the tests to avoid writing any files:'
git ls-files --others --exclude-standard
echo
exit 1
