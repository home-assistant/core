# -*- mode: ruby -*-
# vi: set ft=ruby :

# All Vagrant configuration is done below. The "2" in Vagrant.configure
# configures the configuration version (we support older styles for
# backwards compatibility). Please don't change it unless you know what
# you're doing.
Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/trusty64"
  config.vm.network "forwarded_port", guest: 8123, host: 8123
  config.vm.synced_folder ".", "/vagrant"
  config.vm.provision "shell", inline: <<-SHELL
   sudo apt-get update
   sudo apt-get install -y --no-install-recommends nmap net-tools cython3 libudev-dev sudo libglib2.0-dev openssl python3-pip libyaml-dev python3-dev
   sudo mkdir -p /usr/local/share/python-openzwave
   sudo ln -sf /usr/src/app/build/python-openzwave/openzwave/config /usr/local/share/python-openzwave/config
   cd /vagrant
   sudo pip3 install tox
   sudo pip3 install -r requirements_all.txt
   python3 -m homeassistant --daemon -c /vagrant/config
  SHELL
end
