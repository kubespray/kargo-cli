#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Kargo.
#
#    Kargo is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Foobar is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Foobar.  If not, see <http://www.gnu.org/licenses/>.

"""
kargo.cloud
~~~~~~~~~~~~

Run Instances on cloud providers and generate inventory
"""

import sys
import os
import yaml
import json
from kargo.inventory import CfgInventory
from kargo.common import get_logger, query_yes_no, run_command, which, id_generator, get_cluster_name
from ansible.utils.display import Display
display = Display()
playbook_exec = which('ansible-playbook')

try:
    import configparser
except ImportError:
    import ConfigParser as configparser


class Cloud(object):
    '''
    Run Instances on cloud providers and generates inventory
    '''
    def __init__(self, options, cloud):
        self.options = options
        self.cloud = cloud
        self.inventorycfg = options['inventory_path']
        self.playbook = os.path.join(options['kargo_path'], 'local.yml')
        self.cparser = configparser.ConfigParser(allow_no_value=True)
        self.Cfg = CfgInventory(options, cloud)
        self.localcfg = os.path.join(
            options['kargo_path'],
            'inventory/local.cfg'
        )
        self.instances = {'masters':
                          {'file': os.path.join(
                           options['kargo_path'], 'masters_instances.json'),
                           'json': None
                           },
                          'nodes':
                          {'file': os.path.join(
                           options['kargo_path'], 'nodes_instances.json'),
                           'json': None
                           },
                          'etcds':
                          {'file': os.path.join(
                           options['kargo_path'], 'etcds_instances.json'),
                           'json': None
                           },
                          }
        self.logger = get_logger(
            options.get('logfile'),
            options.get('loglevel')
        )
        self.pbook_content = [{
            'gather_facts': False,
            'hosts': 'localhost',
            'become': False,
            'tasks': []
        }]
        self.logger.debug('''
             The following options were used to generate the inventory: %s
             ''' % self.options)

    def write_local_inventory(self):
        '''Generates inventory for local tasks'''
        self.cparser.add_section('local')
        self.cparser.set(
            'local',
            'localhost ansible_python_interpreter=python2 ansible_connection=local'
        )
        try:
            with open(self.localcfg, 'wb') as f:
                self.cparser.write(f)
        except IOError as e:
            display.error(
                'Cannot write inventory %s: %s'
                % (self.localcfg, e)
            )
            sys.exit(1)

    def write_playbook(self):
        '''Write the playbook for instances creation'''
        try:
            with open(self.playbook, "w") as pb:
                pb.write(yaml.dump(self.pbook_content, default_flow_style=True))
        except IOError as e:
            display.error(
                'Cant write the playbook %s: %s'
                % (self.playbook, e)
            )
            sys.exit(1)

    def write_inventory(self):
        '''Generate the inventory according the instances created'''
        for role in ['masters', 'nodes', 'etcds']:
            if '%s_count' % role in self.options.keys():
                with open(self.instances['%s' % role]['file']) as f:
                    self.instances['%s' % role]['json'] = json.load(f)
        self.Cfg.write_inventory(self.instances['masters']['json'], self.instances['nodes']['json'], self.instances['etcds']['json'])

    def create_instances(self):
        '''Run ansible-playbook for instances creation'''
        cmd = [
            playbook_exec, '-i', self.localcfg, '-e',
            'ansible_connection=local', self.playbook
        ]
        if not self.options['assume_yes']:
            count = 0
            for role in ['masters', 'nodes', 'etcds']:
                if '%s_count' % role in self.options.keys():
                    count = count + self.options['%s_count' % role]
            if self.options['add_node']:
                display.warning(
                    '%s node(s) will be added to the current inventory %s' %
                    (count, self.inventorycfg)
                )
            if not query_yes_no('Create %s instances on %s ?' % (count, self.cloud)):
                display.display('Aborted', color='red')
                sys.exit(1)
        rcode, emsg = run_command('Create %s instances' % self.cloud, cmd)
        if rcode != 0:
            self.logger.critical('Cannot create instances: %s' % emsg)
            sys.exit(1)


class AWS(Cloud):

    def __init__(self, options):
        Cloud.__init__(self, options, "aws")
        self.options = options

    def gen_ec2_playbook(self):
        data = self.options
        data.pop('func')
        # Options list of ansible EC2 module
        self.options['image'] = self.options['ami']
        if 'security_group_id' in self.options.keys():
            self.options['group_id'] = self.options['security_group_id']
        if 'security_group_name' in self.options.keys():
            self.options['group'] = self.options['security_group_name']
        if 'tags' in self.options:
            self.options['instance_tags'] = {}
            for kv in self.options['tags']:
                k, v = kv.split("=")
                self.options['instance_tags'][k] = v
        ec2_options = [
            'aws_access_key', 'aws_secret_key', 'count', 'group_id',
            'group', 'instance_type', 'key_name', 'vpc_subnet_id',
            'image', 'instance_tags', 'assign_public_ip', 'region'
        ]
        # Define EC2 task
        for role in ['masters', 'nodes', 'etcds']:
            if '%s_count' % role in self.options.keys():
                ec2_task = {'ec2': {},
                            'name': 'Provision EC2 %s instances' % role,
                            'register': 'ec2_%s' % role}
                for opt in ec2_options:
                    if opt in self.options.keys():
                        d = {opt: self.options[opt]}
                        ec2_task['ec2'].update(d)
                ec2_task['ec2'].update({'count': self.options['%s_count' % role]})
                ec2_task['ec2'].update({'instance_type': self.options['%s_instance_type' % role]})
                ec2_task['ec2'].update({'wait': True})
                self.pbook_content[0]['tasks'].append(ec2_task)
                # Write ec2 instances json
                self.pbook_content[0]['tasks'].append(
                    {'name': 'Generate a file with ec2 instances list',
                     'copy':
                         {'dest': '%s' % self.instances['%s' % role]['file'],
                          'content': '{{ec2_%s.instances}}' % role}}
                )
                # Wait for ssh task
                if self.options['use_private_ip']:
                    instance_ip = '{{ item.private_ip }}'
                else:
                    instance_ip = '{{ item.public_ip }}'
                self.pbook_content[0]['tasks'].append(
                    {'local_action': {'host': '%s' % instance_ip,
                                      'module': 'wait_for',
                                      'port': 22,
                                      'state': 'started',
                                      'timeout': 600},
                     'name': 'Wait until SSH is available',
                     'with_items': '{{ec2_%s.instances}}' % role}
                )
        self.write_local_inventory()
        self.write_playbook()


class GCE(Cloud):

    def __init__(self, options):
        Cloud.__init__(self, options, "gce")
        self.options = options

    def gen_gce_playbook(self):
        data = self.options
        data.pop('func')
        if 'tags' in self.options:
            self.options['tags'] = ','.join(self.options['tags'])
        # Options list of ansible GCE module
        gce_options = [
            'machine_type', 'image', 'zone', 'service_account_email',
            'pem_file', 'project_id', 'tags'
        ]
        # Define instance names
        cluster_name = 'k8s-' + get_cluster_name()
        for role in ['masters', 'nodes', 'etcds']:
            gce_instance_names = list()
            if '%s_count' % role in self.options.keys():
                for x in range(self.options['%s_count' % role]):
                    if self.options['add_node']:
                        current_inventory = self.Cfg.read_inventory()
                        cluster_name = '-'.join(
                            current_inventory['all']['hosts'][0]['hostname'].split('-')[:-2]
                        )
                        gce_instance_names.append(
                            cluster_name + '-%s' % id_generator()
                        )
                    elif 'cluster_name' in self.options.keys():
                        gce_instance_names.append(
                            self.options['cluster_name'] + '-%s' % id_generator()
                        )
                    else:
                        gce_instance_names.append(
                            cluster_name + '-%s' % id_generator()
                        )
                gce_instance_names = ','.join(gce_instance_names)
                # Define GCE task
                gce_task = {'gce': {},
                            'name': 'Provision GCE %s instances' % role,
                            'register': 'gce_%s' % role}
                for opt in gce_options:
                    if opt in self.options.keys():
                        d = {opt: self.options[opt]}
                        gce_task['gce'].update(d)
                gce_task['gce'].update({'machine_type': self.options['%s_machine_type' % role]})
                gce_task['gce'].update({'instance_names': '%s' % gce_instance_names})
                self.pbook_content[0]['tasks'].append(gce_task)
                # Write gce instances json
                self.pbook_content[0]['tasks'].append(
                    {'name': 'Generate a file with %s list' % role,
                     'copy':
                         {'dest': '%s' % self.instances['%s' % role]['file'],
                          'content': '{{gce_%s.instance_data}}' % role}}
                )
                # Wait for ssh task
                self.pbook_content[0]['tasks'].append(
                    {'local_action': {'host': '{{ item.public_ip }}',
                                      'module': 'wait_for',
                                      'port': 22,
                                      'state': 'started',
                                      'timeout': 600},
                     'name': 'Wait until SSH is available',
                     'with_items': '{{gce_%s.instance_data}}' % role}
                )
        self.write_local_inventory()
        self.write_playbook()


class OpenStack(Cloud):
    def __init__(self, options):
        Cloud.__init__(self, options, 'openstack')
        self.options = options

    def gen_openstack_playbook(self):
        data = self.options
        data.pop('func')

        openstack_credential_args = ['auth_url', 'username', 'password', 'project_name']
        openstack_auth = {}

        for cred_arg in openstack_credential_args:
            openstack_auth.update({cred_arg: self.options['os_%s' % cred_arg]})

        if self.options['floating_ip']:
            ip_type = 'public'
        else:
            ip_type = 'private'

        # Define instance names
        cluster_name = 'k8s-' + get_cluster_name()
        os_security_group_name = cluster_name + '-%s' % id_generator()
        os_instance_names = list()

        for x in range(self.options['count']):
            if self.options['add_node']:
                current_inventory = self.Cfg.read_inventory()
                cluster_name = '-'.join(
                    current_inventory['all']['hosts'][0]['hostname'].split('-')[:-1]
                )
                os_instance_names.append(
                    cluster_name + '-%s' % id_generator()
                )
            elif 'cluster_name' in self.options.keys():
                os_instance_names.append(
                    self.options['cluster_name'] + '-%s' % id_generator()
                )
                os_security_group_name = self.options['cluster_name'] + '-%s' % id_generator()
            else:
                os_instance_names.append(
                    cluster_name + '-%s' % id_generator()
                )
        for idx, name in enumerate(os_instance_names):
            if idx < 2:
                os_instance_names[idx] = name + '-m'
            else:
                os_instance_names[idx] = name + '-n'

        self.pbook_content[0]['tasks'].append({'name': 'Create security group',
                                               'os_security_group': {
                                                   'auth': openstack_auth,
                                                   'name': os_security_group_name,
                                                   'description': 'Contains security rules for the Kubernetes cluster',
                                                   'state': 'present'}})

        self.pbook_content[0]['tasks'].append({'name': 'Add security rules',
                                               'os_security_group_rule': {
                                                   'auth': openstack_auth,
                                                   'security_group': os_security_group_name,
                                                   'protocol': '{{item}}',
                                                   'state': 'present'},
                                               'with_items': ['tcp', 'udp', 'icmp']})

        self.pbook_content[0]['tasks'].append({'name': 'Create network ports',
                                               'os_port': {
                                                   'auth': openstack_auth,
                                                   'name': '{{item}}',
                                                   'network': self.options['network'],
                                                   'allowed_address_pairs': [{'ip_address': self.options['kube_network']}],
                                                   'security_groups': [os_security_group_name],
                                                   'state': 'present'},
                                               'with_items': os_instance_names})

        self.pbook_content[0]['tasks'].append({'name': 'Start Instances',
                                               'os_server': {
                                                   'auth': openstack_auth,
                                                   'name': '{{item}}',
                                                   'state': 'present',
                                                   'flavor': self.options['flavor'],
                                                   'key_name': self.options['sshkey'],
                                                   'auto_ip': self.options['floating_ip'],
                                                   'security_groups': [os_security_group_name],
                                                   'nics': 'port-name={{ item }}',
                                                   'image': self.options['image']},
                                               'register': 'nodes',
                                               'with_items': os_instance_names})

        self.pbook_content[0]['tasks'].append({'name': 'Wait until instances are ready',
                                               'wait_for': {
                                                   'host': '{{item.openstack.%s_v4}}' % ip_type,
                                                   'port': 22,
                                                   'search_regex': 'SSH',
                                                   'state': 'started',
                                                   'delay': 10},
                                               'with_items': '{{nodes.results}}'})

        self.pbook_content[0]['tasks'].append({'name': 'Generate OpenStack instances file',
                                               'copy': {'dest': '%s' % self.instances_file,
                                                        'content': '{{nodes}}'}})
        self.write_local_inventory()
        self.write_playbook()
