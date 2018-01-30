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
kubespray.inventory
~~~~~~~~~~~~

Ansible inventory management for Kubespray
"""

import sys
import re
from kubespray.common import get_logger, id_generator, get_cluster_name
from ansible.utils.display import Display
display = Display()

try:
    import configparser
except ImportError:
    import ConfigParser as configparser


class CfgInventory(object):
    '''
    Read classic ansible inventory file.
    '''

    def __init__(self, options, platform):
        self.options = options
        self.platform = platform
        self.inventorycfg = options['inventory_path']
        self.logger = get_logger(options.get('logfile'), options.get('loglevel'))
        self.cparser = configparser.ConfigParser(allow_no_value=True)
        self.inventory = {'all': {'hosts': []},
                          'kube-master': {'hosts': []},
                          'etcd': {'hosts': []},
                          'kube-node': {'hosts': []},
                          'k8s-cluster:children': {'hosts': [
                              {'hostname': 'kube-node', 'hostvars': []},
                              {'hostname': 'kube-master', 'hostvars': []}
                          ]},
                          }

    def read_inventory(self):
        read_cparser = configparser.ConfigParser(allow_no_value=True)
        try:
            read_cparser.read(self.inventorycfg)
        except IOError as e:
            display.error('Cannot read configuration %s: %s'
                          % (self.options['inventory_path'], e)
                          )
            sys.exit(1)
        expected_sections = ['kube-node', 'kube-master', 'all', 'etcd', 'k8s-cluster:children']
        for k in expected_sections:
            if k not in read_cparser.sections():
                display.error(
                    'The config file %s doesn\'t have a section named %s'
                    % (self.options['inventory_path'], k)
                )
                sys.exit(1)
        current_inventory = {'all': {'hosts': []},
                             'kube-master': {'hosts': []},
                             'etcd': {'hosts': []},
                             'kube-node': {'hosts': []},
                             'k8s-cluster:children': {'hosts': [
                                 {'hostname': 'kube-node', 'hostvars': []},
                                 {'hostname': 'kube-master', 'hostvars': []}
                             ]},
                             }
        for section in current_inventory.keys():
            for line, properties_str in read_cparser.items(section):
                machine_part = line.split('#', 1)[0]  # get rid of comments parts
                machine_part = line.split(None, 1)
                inventory_hostname = machine_part[0]
                host_dict = {'hostname': '', 'hostvars': []}
                hostvars = []
                if len(machine_part) == 2:
                    if properties_str:
                        properties_str = machine_part[1] + '=' + properties_str
                    else:
                        properties_str = machine_part[1]
                    for hostvar in properties_str.split():
                        name, value = hostvar.split('=')
                        d = {'name': name, 'value': value}
                        hostvars.append(d)
                host_dict['hostname'] = inventory_hostname
                host_dict['hostvars'] = hostvars
                current_inventory[section]['hosts'].append(host_dict)
        return(current_inventory)

    def format_inventory(self, masters, nodes, etcds):
        new_inventory = {'all': {'hosts': []},
                         'kube-master': {'hosts': []},
                         'etcd': {'hosts': []},
                         'kube-node': {'hosts': []},
                         'k8s-cluster:children': {'hosts': [
                             {'hostname': 'kube-node', 'hostvars': []},
                             {'hostname': 'kube-master', 'hostvars': []}
                             ]},
                         }

        if self.platform == 'openstack':
            if self.options['floating_ip']:
                ip_type = 'public_v4'
            else:
                ip_type = 'private_v4'
            # handle masters
            new_instances = []
            for master in masters:
                new_instances.append({'public_ip': master['openstack'][ip_type],
                                      'name': master['item']})
            masters = new_instances
            # handle nodes
            new_instances = []
            for node in nodes:
                new_instances.append({'public_ip': node['openstack'][ip_type],
                                      'name': node['item']})
            nodes = new_instances
            # handle etcds
            new_instances = []
            for etcd in etcds:
                new_instances.append({'public_ip': etcd['openstack'][ip_type],
                                      'name': etcd['item']})
            etcds = new_instances

        if not self.options['add_node']:
            if not masters and len(nodes) == 1:
                masters = [nodes[0]]
            elif not masters:
                masters = nodes[0:2]
            if not etcds and len(nodes) >= 3:
                etcds = nodes[0:3]
            elif not etcds and len(nodes) < 3:
                etcds = [nodes[0]]
            elif etcds and len(etcds) < 3:
                etcds = [etcds[0]]

        if self.platform in ['aws', 'gce', 'openstack']:
            if self.options['add_node']:
                current_inventory = self.read_inventory()
                cluster_name = '-'.join(
                    current_inventory['all']['hosts'][0]['hostname'].split('-')[:-1]
                )
                new_inventory = current_inventory
            else:
                cluster_name = 'k8s-' + get_cluster_name()
            if self.options['use_private_ip']:
                instance_ip = 'private_ip'
            else:
                instance_ip = 'public_ip'
            for host in nodes + masters + etcds:
                if self.platform == 'aws':
                    host['name'] = "%s-%s" % (cluster_name, id_generator(5))
                new_inventory['all']['hosts'].append(
                    {'hostname': '%s' % host['name'], 'hostvars': [
                        {'name': 'ansible_ssh_host', 'value': host[instance_ip]}
                        ]}
                )
            if not self.options['add_node']:
                for host in nodes:
                    new_inventory['kube-node']['hosts'].append(
                        {'hostname': '%s' % host['name'],
                         'hostvars': []}
                    )
                for host in masters:
                    new_inventory['kube-master']['hosts'].append(
                        {'hostname': '%s' % host['name'],
                         'hostvars': []}
                    )
                for host in etcds:
                    new_inventory['etcd']['hosts'].append(
                        {'hostname': '%s' % host['name'],
                         'hostvars': []}
                    )
        elif self.platform == 'metal':
            for host in nodes + masters + etcds:
                if '[' in host:
                    r = re.search('(^.*)\[(.*)\]', host)
                    inventory_hostname = r.group(1)
                    var_str = r.group(2)
                    hostvars = list()
                    for var in var_str.split(','):
                        hostvars.append({'name': var.split('=')[0], 'value': var.split('=')[1]})
                else:
                    inventory_hostname = host
                    hostvars = []
                new_inventory['all']['hosts'].append(
                    {'hostname': inventory_hostname, 'hostvars': hostvars}
                )
            for host in nodes:
                new_inventory['kube-node']['hosts'].append(
                    {'hostname': host.split('[')[0], 'hostvars': []}
                )
            for host in masters:
                new_inventory['kube-master']['hosts'].append(
                    {'hostname': host.split('[')[0], 'hostvars': []}
                )
            for host in etcds:
                new_inventory['etcd']['hosts'].append(
                    {'hostname': host.split('[')[0], 'hostvars': []}
                )
        return(new_inventory)

    def write_inventory(self, masters, nodes, etcds):
        '''Generates inventory'''
        inventory = self.format_inventory(masters, nodes, etcds)
        if not self.options['add_node']:
            if (('masters_count' in self.options.keys() and len(masters) < 2) or
               ('masters_count' not in self.options.keys() and len(nodes) < 2)):
                display.warning('You should set at least 2 masters')
            if (('etcds_count' in self.options.keys() and len(etcds) < 3) or
               ('etcds_count' not in self.options.keys() and len(nodes) < 3)):
                display.warning('You should set at least 3 nodes for etcd clustering')
        open(self.inventorycfg, 'w').close()
        for key, value in inventory.items():
            self.cparser.add_section(key)
            for host in value['hosts']:
                hostvars = str()
                varlist = list()
                for var in host['hostvars']:
                    varlist.append("%s=%s" % (var['name'], var['value']))
                hostvars = " ".join(varlist)
                self.cparser.set(key, "%s\t\t%s" % (host['hostname'], hostvars))
        with open(self.inventorycfg, 'wb') as configfile:
            display.banner('WRITTING INVENTORY')
            self.cparser.write(configfile)
            self.logger.info(
                'the inventory %s was successfuly generated'
                % self.inventorycfg
            )
            self.logger.debug(
                'The following options were used to generate the inventory: %s'
                % self.options
            )
            display.display(
                'Inventory generated : %s'
                % self.inventorycfg, color='green'
            )
