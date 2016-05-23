"""Starts home assistant."""
from __future__ import print_function

import argparse
import os
import platform
import signal
import subprocess
import sys
import threading
import time

from homeassistant.const import (
    __version__,
    EVENT_HOMEASSISTANT_START,
    REQUIRED_PYTHON_VER,
    RESTART_EXIT_CODE,
)


def validate_python():
    """Validate we're running the right Python version."""
    major, minor = sys.version_info[:2]
    req_major, req_minor = REQUIRED_PYTHON_VER

    if major < req_major or (major == req_major and minor < req_minor):
        print("Home Assistant requires at least Python {}.{}".format(
            req_major, req_minor))
        sys.exit(1)


def ensure_config_path(config_dir):
    """Validate the configuration directory."""
    import homeassistant.config as config_util
    lib_dir = os.path.join(config_dir, 'deps')

    # Test if configuration directory exists
    if not os.path.isdir(config_dir):
        if config_dir != config_util.get_default_config_dir():
            print(('Fatal Error: Specified configuration directory does '
                   'not exist {} ').format(config_dir))
            sys.exit(1)

        try:
            os.mkdir(config_dir)
        except OSError:
            print(('Fatal Error: Unable to create default configuration '
                   'directory {} ').format(config_dir))
            sys.exit(1)

    # Test if library directory exists
    if not os.path.isdir(lib_dir):
        try:
            os.mkdir(lib_dir)
        except OSError:
            print(('Fatal Error: Unable to create library '
                   'directory {} ').format(lib_dir))
            sys.exit(1)


def ensure_config_file(config_dir):
    """Ensure configuration file exists."""
    import homeassistant.config as config_util
    config_path = config_util.ensure_config_exists(config_dir)

    if config_path is None:
        print('Error getting configuration path')
        sys.exit(1)

    return config_path


def get_arguments():
    """Get parsed passed in arguments."""
    import homeassistant.config as config_util
    parser = argparse.ArgumentParser(
        description="Home Assistant: Observe, Control, Automate.")
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument(
        '-c', '--config',
        metavar='path_to_config_dir',
        default=config_util.get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration")
    parser.add_argument(
        '--demo-mode',
        action='store_true',
        help='Start Home Assistant in demo mode')
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Start Home Assistant in debug mode')
    parser.add_argument(
        '--open-ui',
        action='store_true',
        help='Open the webinterface in a browser')
    parser.add_argument(
        '--skip-pip',
        action='store_true',
        help='Skips pip install of required packages on startup')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="Enable verbose logging to file.")
    parser.add_argument(
        '--pid-file',
        metavar='path_to_pid_file',
        default=None,
        help='Path to PID file useful for running as daemon')
    parser.add_argument(
        '--log-rotate-days',
        type=int,
        default=None,
        help='Enables daily log rotation and keeps up to the specified days')
    parser.add_argument(
        '--install-osx',
        action='store_true',
        help='Installs as a service on OS X and loads on boot.')
    parser.add_argument(
        '--uninstall-osx',
        action='store_true',
        help='Uninstalls from OS X.')
    parser.add_argument(
        '--restart-osx',
        action='store_true',
        help='Restarts on OS X.')
    parser.add_argument(
        '--runner',
        action='store_true',
        help='On restart exit with code {}'.format(RESTART_EXIT_CODE))
    if os.name == "posix":
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Run Home Assistant as daemon')

    arguments = parser.parse_args()
    if os.name != "posix" or arguments.debug or arguments.runner:
        arguments.daemon = False

    return arguments


def daemonize():
    """Move current process to daemon process."""
    # Create first fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Decouple fork
    os.setsid()

    # Create second fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # redirect standard file descriptors to devnull
    infd = open(os.devnull, 'r')
    outfd = open(os.devnull, 'a+')
    sys.stdout.flush()
    sys.stderr.flush()
    os.dup2(infd.fileno(), sys.stdin.fileno())
    os.dup2(outfd.fileno(), sys.stdout.fileno())
    os.dup2(outfd.fileno(), sys.stderr.fileno())


def check_pid(pid_file):
    """Check that HA is not already running."""
    # Check pid file
    try:
        pid = int(open(pid_file, 'r').readline())
    except IOError:
        # PID File does not exist
        return

    # If we just restarted, we just found our own pidfile.
    if pid == os.getpid():
        return

    try:
        os.kill(pid, 0)
    except OSError:
        # PID does not exist
        return
    print('Fatal Error: HomeAssistant is already running.')
    sys.exit(1)


def write_pid(pid_file):
    """Create a PID File."""
    pid = os.getpid()
    try:
        open(pid_file, 'w').write(str(pid))
    except IOError:
        print('Fatal Error: Unable to write pid file {}'.format(pid_file))
        sys.exit(1)


def install_osx():
    """Setup to run via launchd on OS X."""
    with os.popen('which hass') as inp:
        hass_path = inp.read().strip()

    with os.popen('whoami') as inp:
        user = inp.read().strip()

    cwd = os.path.dirname(__file__)
    template_path = os.path.join(cwd, 'startup', 'launchd.plist')

    with open(template_path, 'r', encoding='utf-8') as inp:
        plist = inp.read()

    plist = plist.replace("$HASS_PATH$", hass_path)
    plist = plist.replace("$USER$", user)

    path = os.path.expanduser("~/Library/LaunchAgents/org.homeassistant.plist")

    try:
        with open(path, 'w', encoding='utf-8') as outp:
            outp.write(plist)
    except IOError as err:
        print('Unable to write to ' + path, err)
        return

    os.popen('launchctl load -w -F ' + path)

    print("Home Assistant has been installed. \
        Open it here: http://localhost:8123")


def uninstall_osx():
    """Unload from launchd on OS X."""
    path = os.path.expanduser("~/Library/LaunchAgents/org.homeassistant.plist")
    os.popen('launchctl unload ' + path)

    print("Home Assistant has been uninstalled.")


def closefds_osx(min_fd, max_fd):
    """Make sure file descriptors get closed when we restart.

    We cannot call close on guarded fds, and we cannot easily test which fds
    are guarded. But we can set the close-on-exec flag on everything we want to
    get rid of.
    """
    from fcntl import fcntl, F_GETFD, F_SETFD, FD_CLOEXEC

    for _fd in range(min_fd, max_fd):
        try:
            val = fcntl(_fd, F_GETFD)
            if not val & FD_CLOEXEC:
                fcntl(_fd, F_SETFD, val | FD_CLOEXEC)
        except IOError:
            pass


def cmdline():
    """Collect path and arguments to re-execute the current hass instance."""
    if sys.argv[0].endswith('/__main__.py'):
        modulepath = os.path.dirname(sys.argv[0])
        os.environ['PYTHONPATH'] = os.path.dirname(modulepath)
    return [sys.executable] + [arg for arg in sys.argv if arg != '--daemon']


def setup_and_run_hass(config_dir, args):
    """Setup HASS and run."""
    from homeassistant import bootstrap

    # Run a simple daemon runner process on Windows to handle restarts
    if os.name == 'nt' and '--runner' not in sys.argv:
        args = cmdline() + ['--runner']
        while True:
            try:
                subprocess.check_call(args)
                sys.exit(0)
            except subprocess.CalledProcessError as exc:
                if exc.returncode != RESTART_EXIT_CODE:
                    sys.exit(exc.returncode)

    if args.demo_mode:
        config = {
            'frontend': {},
            'demo': {}
        }
        hass = bootstrap.from_config_dict(
            config, config_dir=config_dir, verbose=args.verbose,
            skip_pip=args.skip_pip, log_rotate_days=args.log_rotate_days)
    else:
        config_file = ensure_config_file(config_dir)
        print('Config directory:', config_dir)
        hass = bootstrap.from_config_file(
            config_file, verbose=args.verbose, skip_pip=args.skip_pip,
            log_rotate_days=args.log_rotate_days)

    if hass is None:
        return

    if args.open_ui:
        def open_browser(event):
            """Open the webinterface in a browser."""
            if hass.config.api is not None:
                import webbrowser
                webbrowser.open(hass.config.api.base_url)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, open_browser)

    print('Starting Home-Assistant')
    hass.start()
    exit_code = int(hass.block_till_stopped())

    return exit_code


def try_to_restart():
    """Attempt to clean up state and start a new homeassistant instance."""
    # Things should be mostly shut down already at this point, now just try
    # to clean up things that may have been left behind.
    sys.stderr.write('Home Assistant attempting to restart.\n')

    # Count remaining threads, ideally there should only be one non-daemonized
    # thread left (which is us). Nothing we really do with it, but it might be
    # useful when debugging shutdown/restart issues.
    try:
        nthreads = sum(thread.isAlive() and not thread.isDaemon()
                       for thread in threading.enumerate())
        if nthreads > 1:
            sys.stderr.write(
                "Found {} non-daemonic threads.\n".format(nthreads))

    # Somehow we sometimes seem to trigger an assertion in the python threading
    # module. It seems we find threads that have no associated OS level thread
    # which are not marked as stopped at the python level.
    except AssertionError:
        sys.stderr.write("Failed to count non-daemonic threads.\n")

    # Send terminate signal to all processes in our process group which
    # should be any children that have not themselves changed the process
    # group id. Don't bother if couldn't even call setpgid.
    if hasattr(os, 'setpgid'):
        sys.stderr.write("Signalling child processes to terminate...\n")
        os.kill(0, signal.SIGTERM)

        # wait for child processes to terminate
        try:
            while True:
                time.sleep(1)
                if os.waitpid(0, os.WNOHANG) == (0, 0):
                    break
        except OSError:
            pass

    elif os.name == 'nt':
        # Maybe one of the following will work, but how do we indicate which
        # processes are our children if there is no process group?
        # os.kill(0, signal.CTRL_C_EVENT)
        # os.kill(0, signal.CTRL_BREAK_EVENT)
        pass

    # Try to not leave behind open filedescriptors with the emphasis on try.
    try:
        max_fd = os.sysconf("SC_OPEN_MAX")
    except ValueError:
        max_fd = 256

    if platform.system() == 'Darwin':
        closefds_osx(3, max_fd)
    else:
        os.closerange(3, max_fd)

    # Now launch into a new instance of Home-Assistant. If this fails we
    # fall through and exit with error 100 (RESTART_EXIT_CODE) in which case
    # systemd will restart us when RestartForceExitStatus=100 is set in the
    # systemd.service file.
    sys.stderr.write("Restarting Home-Assistant\n")
    args = cmdline()
    os.execv(args[0], args)


def main():
    """Start Home Assistant."""
    validate_python()

    args = get_arguments()

    config_dir = os.path.join(os.getcwd(), args.config)
    ensure_config_path(config_dir)

    # OS X launchd functions
    if args.install_osx:
        install_osx()
        return 0
    if args.uninstall_osx:
        uninstall_osx()
        return 0
    if args.restart_osx:
        uninstall_osx()
        # A small delay is needed on some systems to let the unload finish.
        time.sleep(0.5)
        install_osx()
        return 0

    # Daemon functions
    if args.pid_file:
        check_pid(args.pid_file)
    if args.daemon:
        daemonize()
    if args.pid_file:
        write_pid(args.pid_file)

    # Create new process group if we can
    if hasattr(os, 'setpgid'):
        try:
            os.setpgid(0, 0)
        except PermissionError:
            pass

    exit_code = setup_and_run_hass(config_dir, args)
    if exit_code == RESTART_EXIT_CODE and not args.runner:
        try_to_restart()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
