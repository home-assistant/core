"""Home Assistant command line scripts."""
import importlib
import os


def run(args: str) -> int:
    """Run a script."""
    scripts = []
    path = os.path.dirname(__file__)
    for fil in os.listdir(path):
        if fil == '__pycache__':
            continue
        elif os.path.isdir(os.path.join(path, fil)):
            scripts.append(fil)
        elif fil != '__init__.py' and fil.endswith('.py'):
            scripts.append(fil[:-3])

    if not args:
        print('Please specify a script to run.')
        print('Available scripts:', ', '.join(scripts))
        return 1

    if args[0] not in scripts:
        print('Invalid script specified.')
        print('Available scripts:', ', '.join(scripts))
        return 1

    script = importlib.import_module('homeassistant.scripts.' + args[0])
    return script.run(args[1:])  # type: ignore
