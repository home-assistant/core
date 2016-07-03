"""Home Assistant command line scripts."""
import importlib
import os


def run(args):
    """Run a script."""
    scripts = [fil[:-3] for fil in os.listdir(os.path.dirname(__file__))
               if fil.endswith('.py') and fil != '__init__.py']

    if not args:
        print('Please specify a script to run.')
        print('Available scripts:', ', '.join(scripts))
        return 1

    if args[0] not in scripts:
        print('Invalid script specified.')
        print('Available scripts:', ', '.join(scripts))
        return 1

    script = importlib.import_module('homeassistant.scripts.' + args[0])
    return script.run(args[1:])
