#!/bin/sh

if [ "$username" = "good-user" ] && [ "$password" = "good-pass" ]; then
	echo "Auth should succeed." >&2
	if [ "$1" = "--with-meta" ]; then
		echo "name=Bob"
		echo "group=system-users"
		echo "local_only=true"
	elif [ "$1" = "--with-meta-remote" ]; then
		echo "name=Bob"
		echo "group=system-users"
		echo "local_only=false"
	elif [ "$1" = "--with-empty-name" ]; then
		echo "name="
		echo "group="
		echo "local_only=true"
	elif [ "$1" = "--with-invalid-local-only" ]; then
		echo "name=Bob"
		echo "group=system-users"
		echo "local_only=invalid"
	fi
	exit 0
fi

echo "Auth should fail." >&2
exit 1
