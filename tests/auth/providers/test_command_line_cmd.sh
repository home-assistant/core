#!/bin/sh

if [ "$username" = "good-user" ] && [ "$password" = "good-pass" ]; then
	echo "Auth should succeed." >&2
	if [ "$1" = "--with-meta" ]; then
		echo "name=Bob"
		echo "group=system-users"
		echo "local_only=true"
	fi
	exit 0
fi

echo "Auth should fail." >&2
exit 1
