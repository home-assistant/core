"""Home Assistant scripts."""

from probatio.compat import install_as_voluptuous

# Scripts such as hassfest (and the libraries they import) use voluptuous. Alias it
# to probatio before anything imports it, the same as homeassistant/__init__.py does
# for the application itself. This must run before the first `import voluptuous`.
install_as_voluptuous()
