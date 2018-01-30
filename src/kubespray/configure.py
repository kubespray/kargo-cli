#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Kubespray.
#
#    Kubespray is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Kubespray is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Kubespray.  If not, see <http://www.gnu.org/licenses/>.

"""
kubespray.configure
~~~~~~~~~~~~

Configuration management for Kubespray
"""
import sys
import os
import yaml
from ansible.utils.display import Display
from kubespray.common import read_password


class Config(object):

    def __init__(self, configfile):
        self.display = Display()
        self.configfile = configfile
        self.logfile = None
        self.loglevel = None

    @property
    def parse_configfile(self):
        """
        Retrieve configuration parameters from the config file
        """
        try:
            with open(self.configfile, "r") as f:
                config = yaml.load(f)
        except:
            self.display.error(
                "Can't read configuration file %s" % self.configfile
            )
            sys.exit(1)
        return config

    def default_values(self, args, config):
        # Set kubespray_path
        if 'kubespray_path' not in config.keys() and args.kubespray_path is None:
            config['kubespray_path'] = os.path.join(os.path.expanduser("~"), '.kubespray')
        arguments = dict(args._get_kwargs())
        for key, value in arguments.items():
            if value is not None:
                config[key] = value
        # Set inventory_path
        if 'inventory_path' not in config.keys() and args.inventory_path is None:
            config['inventory_path'] = os.path.join(
                config['kubespray_path'], 'inventory/inventory.cfg'
            )
        # Set logfile
        if 'logfile' not in config.keys():
            config['logfile'] = os.path.join(config['kubespray_path'], 'kubespray.log')
        # Set default bool
        for v in ['use_private_ip', 'assign_public_ip']:
            if v not in config.keys():
                config[v] = False
        # Set default instances type
        if args.func.__name__ == "aws":
            if 'masters_instance_type' not in config.keys() and args.masters_instance_type is None:
                config['masters_instance_type'] = 't2.medium'
            if 'nodes_instance_type' not in config.keys() and args.nodes_instance_type is None:
                config['nodes_instance_type'] = 't2.large'
            if 'etcds_instance_type' not in config.keys() and args.etcds_instance_type is None:
                config['etcds_instance_type'] = 't2.small'
        # ----GCE
        if args.func.__name__ == "gce":
            if 'masters_machine_type' not in config.keys() and args.masters_machine_type is None:
                config['masters_machine_type'] = 'n1-standard-2'
            if 'nodes_machine_type' not in config.keys() and args.nodes_machine_type is None:
                config['nodes_machine_type'] = 'n1-standard-4'
            if 'etcds_machine_type' not in config.keys() and args.etcds_machine_type is None:
                config['etcds_machine_type'] = 'n1-standard-1'
        # Conflicting options
        if args.func.__name__ == "aws":
            if args.security_group_name and 'security_group_id' in config.keys():
                config.pop('security_group_id')
            elif args.security_group_id and 'security_group_name' in config.keys():
                config.pop('security_group_name')
        # Set kubernetes 'kube' password
        if 'prompt_pwd' in config.keys() and config['prompt_pwd'] is True:
            pwd = read_password()
            config['k8s_passwd'] = pwd
        return(config)
