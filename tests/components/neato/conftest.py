"""Skip test collection due to urllib3 compatibility."""

# See https://github.com/stianaske/pybotvac/issues/92

collect_ignore_glob = ["test_*.py"]
