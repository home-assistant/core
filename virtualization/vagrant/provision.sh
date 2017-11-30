#!/bin/bash
set -e

readonly SETUP_DONE='/home-assistant/virtualization/vagrant/setup_done'
readonly RUN_TESTS='/home-assistant/virtualization/vagrant/run_tests'
readonly RESTART='/home-assistant/virtualization/vagrant/restart'

usage() {
    echo '############################################################

Use `./provision.sh` to interact with HASS. E.g:

- setup the environment: `./provision.sh start`
- restart HASS process: `./provision.sh restart`
- run test suit: `./provision.sh tests`
- destroy the host and start anew: `./provision.sh recreate`

Official documentation at https://home-assistant.io/docs/installation/vagrant/

############################################################'
}

print_done() {
    echo '############################################################


HASS running => http://localhost:8123/

'
}

setup_error() {
    echo '############################################################
Something is off... maybe setup did not complete properly?
Please ensure setup did run correctly at least once.

To run setup again: `./provision.sh setup`

############################################################'
    exit 1
}

setup() {
    local hass_path='/root/venv/bin/hass'
    local systemd_bin_path='/usr/bin/hass'
    # Setup systemd
    cp /home-assistant/virtualization/vagrant/home-assistant@.service \
        /etc/systemd/system/home-assistant.service
    systemctl --system daemon-reload
    systemctl enable home-assistant
    systemctl stop home-assistant
    # Install packages
    apt-get update
    apt-get install -y git rsync python3-dev python3-pip libssl-dev libffi-dev
    pip3 install --upgrade virtualenv
    virtualenv ~/venv
    source ~/venv/bin/activate
    pip3 install --upgrade tox
    /home-assistant/script/setup
    if ! [ -f $systemd_bin_path ]; then
        ln -s $hass_path $systemd_bin_path
    fi
    touch $SETUP_DONE
    print_done
    usage
}

run_tests() {
    rm -f $RUN_TESTS
    echo '############################################################'
    echo; echo "Running test suite, hang on..."; echo; echo
    if ! systemctl stop home-assistant; then
        setup_error
    fi
    source ~/venv/bin/activate
    rsync -a --delete \
        --exclude='*.tox' \
        --exclude='*.git' \
        /home-assistant/ /home-assistant-tests/
    cd /home-assistant-tests && tox || true
    echo '############################################################'
}

restart() {
    echo "Restarting Home Assistant..."
    if ! systemctl restart home-assistant; then
        setup_error
    else
        echo "done"
    fi
    rm $RESTART
}

main() {
    # If a parameter is provided, we assume it's the user interacting
    # with the provider script...
    case $1 in
        "setup") rm -f setup_done; vagrant up --provision && touch setup_done; exit ;;
        "tests") touch run_tests; vagrant provision ; exit ;;
        "restart") touch restart; vagrant provision ; exit ;;
        "start") vagrant up --provision ; exit ;;
        "stop") vagrant halt ; exit ;;
        "destroy") vagrant destroy -f ; exit ;;
        "recreate") rm -f setup_done restart; vagrant destroy -f; \
                    vagrant up --provision; exit ;;
    esac
    # ...otherwise we assume it's the Vagrant provisioner
    if [ $(hostname) != "contrib-jessie" ]; then usage; exit; fi
    if ! [ -f $SETUP_DONE ]; then setup; fi
    if [ -f $RESTART ]; then restart; fi
    if [ -f $RUN_TESTS ]; then run_tests; fi
    if ! systemctl start home-assistant; then
        setup_error
    fi
}

main $*
