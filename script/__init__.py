"""Home Assistant scripts."""

import contextlib

# Scripts such as hassfest (and the libraries they import) use voluptuous. Alias it
# to probatio before anything imports it, the same as homeassistant/__init__.py does
# for the application itself. This must run before the first `import voluptuous`.
# Some scripts (for example check_requirements) run before dependencies are
# installed, so probatio may be absent; those scripts do not need the alias.
with contextlib.suppress(ImportError):
    from probatio.compat import install_as_voluptuous

    install_as_voluptuous()
