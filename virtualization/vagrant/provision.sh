#!/bin/bash
set -e

readonly SETUP_DONE='/home-assistant/virtualization/vagrant/setup_done'
readonly RUN_TESTS='/home-assistant/virtualization/vagrant/run_tests'
readonly RESTART='/home-assistant/virtualization/vagrant/restart'

usage() {
    echo '############################################################
############################################################
############################################################

Use `vagrant provision` to either run tests or restart HASS:

`touch run_tests && vagrant provision`

or

`touch restart && vagrant provision`

To destroy the host and start anew:

`vagrant destroy -f ; rm setup_done; vagrant up`

############################################################
############################################################
############################################################'
}

print_done() {
    echo '############################################################
############################################################
############################################################


HASS running => http://localhost:8123/

'
}

setup_error() {
    echo '############################################################
Something is off... maybe setup did not complete properly?
Please ensure setup did run correctly at least once.

To run setup again:

`rm setup_done; vagrant provision`

############################################################'
    exit 1
}

setup() {
    local hass_path='/root/venv/bin/hass'
    local systemd_bin_path='/usr/bin/hass'
    # Setup systemd
    cp /home-assistant/script/home-assistant@.service \
        /etc/systemd/system/home-assistant.service
    systemctl --system daemon-reload
    systemctl enable home-assistant
    # Install packages
    apt-get update
    apt-get install -y git rsync python3-dev python3-pip
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
    if ! systemctl stop home-assistant; then
        setup_error
    fi
    source ~/venv/bin/activate
    rsync -a --delete \
        --exclude='*.tox' \
        --exclude='*.git' \
        /home-assistant/ /home-assistant-tests/
    cd /home-assistant-tests && tox
    rm $RUN_TESTS
}

restart() {
    if ! systemctl restart home-assistant; then
        setup_error
    fi
    rm $RESTART
}

main() {
    if ! [ -f $SETUP_DONE ]; then setup; fi
    if [ -f $RUN_TESTS ]; then run_tests; fi
    if [ -f $RESTART ]; then restart; fi
    if ! systemctl start home-assistant; then
        setup_error
    fi
}

main
