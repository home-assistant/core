"""Script to find orphan/unused strings in strings.json for all integrations."""

import glob
import json
import os


def dig_recursive(dic: dict, keys: list):
    """Recursively dig into dict looking for key/value = string/string."""
    for key, val in dic.items():
        if type(key) is str:
            if type(val) is str:
                keys.append(key)
            elif type(val) is dict:
                dig_recursive(val, keys)


def find_orphan_strings(basedir, ignores):
    """Find keys referenced in strings.json that aren't used anywhere in code."""

    keys = []  # the keys we're looking for
    with open(os.path.join(basedir, "strings.json")) as _jfile:
        _j = json.loads(_jfile.read())
        dig_recursive(_j, keys)

    sourcelines = []
    for pythonfile in glob.iglob("%s" % basedir + os.sep + "*.py"):
        with open(pythonfile) as pfile:
            for line in pfile:
                line = line.split("#", 1)[0]
                line = line.rstrip()
                sourcelines.append(line)

    _orphans = []  # list of orphans we generate
    for key in keys:
        if key not in ignores and not any(key in s for s in sourcelines + ignores):
            _orphans.append(key)
    return _orphans


if __name__ == "__main__":
    orphancount = 0
    ignorelist = ["description", "title", "flow_title", "already_configured"]

    with open("homeassistant/strings.json") as jfile:
        j = json.loads(jfile.read())
        dig_recursive(j, ignorelist)

    for path in sorted(glob.glob("homeassistant/components/*/strings.json")):
        dirname = os.path.dirname(path)
        if os.path.isfile(os.path.join(dirname, "config_flow.py")):
            orphans = find_orphan_strings(dirname, ignorelist)
            if len(orphans) > 0:
                orphancount += len(orphans)
                print("%s:" % path)
                for orphan in orphans:
                    print(" unused/orphan key '%s'" % orphan)

    print("Total orphan strings = %d" % orphancount)
