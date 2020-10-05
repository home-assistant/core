#!/bin/bash -ex

git diff dev.. homeassistant/components/zabbix > ../homeassistant/homeassistant-zabbix.patch
