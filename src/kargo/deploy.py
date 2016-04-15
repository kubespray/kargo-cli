#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
# This file is part of Kargo.
#
#    Foobar is free software: you can redistribute it and/or modify
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
kargo.deploy
~~~~~~~~~~~~

Deploy a kubernetes cluster. Run the ansible-playbbook
"""

import re
import sys
import os
import signal
import netaddr
from subprocess import PIPE, STDOUT, Popen, check_output, CalledProcessError
from kargo.common import get_logger, query_yes_no, run_command, which, validate_cidr
from ansible.utils.display import Display
display = Display()
playbook_exec = which('ansible-playbook')
ansible_exec = which('ansible')


class RunPlaybook(object):
    '''
    Run the Ansible playbook to deploy the kubernetes cluster
    '''
    def __init__(self, options):
        self.options = options
        self.inventorycfg = options['inventory_path']
        self.logger = get_logger(
            options.get('logfile'),
            options.get('loglevel')
        )
        self.logger.debug(
            'Running ansible-playbook command with the following options: %s'
            % self.options
        )

    def ssh_prepare(self):
        '''
        Run ssh-agent and store identities
        '''
        try:
            sshagent = check_output('ssh-agent')
        except CalledProcessError as e:
            display.error('Cannot run the ssh-agent : %s' % e.output)
        # Set environment variables
        ssh_envars = re.findall('\w*=[\w*-\/.*]*', sshagent)
        for v in ssh_envars:
            os.environ[v.split('=')[0]] = v.split('=')[1]
        # Store ssh identity
        try:
            if 'ssh_key' in self.options.keys():
                cmd = ['ssh-add', os.path.realpath(self.options['ssh_key'])]
            else:
                cmd = 'ssh-add'
            proc = Popen(
                cmd, stdout=PIPE, stderr=STDOUT, stdin=PIPE
            )
            proc.stdin.write('password\n')
            proc.stdin.flush()
            response_stdout, response_stderr = proc.communicate()
            display.display(response_stdout)
        except CalledProcessError as e:
            display.error('Failed to store ssh identity : %s' % e.output)
            sys.exit(1)
        try:
            check_output(['ssh-add', '-l'])
        except CalledProcessError as e:
            display.error('Failed to list identities : %s' % e.output)
            sys.exit(1)
        if response_stderr:
            display.error(response_stderr)
            self.logger.critical(
                'Deployment stopped because of ssh credentials'
                % self.filename
            )
            os.kill(int(os.environ.get('SSH_AGENT_PID')), signal.SIGTERM)
            sys.exit(1)

    def check_ping(self):
        '''
         Check if hosts are reachable
        '''
        display.banner('CHECKING SSH CONNECTIONS')
        cmd = [
            ansible_exec, '--ssh-extra-args', '-o StrictHostKeyChecking=no',
            '-u', '%s' % self.options['ansible_user'],
            '-b', '--become-user=root', '-m', 'ping', 'all',
            '-i', self.inventorycfg
        ]
        if self.options['coreos']:
            cmd = cmd + ['-e', 'ansible_python_interpreter=/opt/bin/python']
        rcode, emsg = run_command('SSH ping hosts', cmd)
        if rcode != 0:
            self.logger.critical('Cannot connect to hosts: %s' % emsg)
            os.kill(int(os.environ.get('SSH_AGENT_PID')), signal.SIGTERM)
            sys.exit(1)
        display.display('All hosts are reachable', color='green')

    def coreos_bootstrap(self):
        '''
        Install python dependencies on CoreOS
        '''
        cmd = [
            playbook_exec, '--ssh-extra-args', '-o StrictHostKeyChecking=no',
            '-e', 'ansible_python_interpreter=/opt/bin/python',
            '-u',  '%s' % self.options['ansible_user'],
            '-b', '--become-user=root', '-i', self.inventorycfg,
            os.path.join(self.options['kargo_path'], 'coreos-bootstrap.yml')
        ]
        display.banner('BOOTSTRAP COREOS')
        self.logger.info(
            'Bootstrapping CoreOS with the command: %s' % cmd
        )
        rcode, emsg = run_command('Bootstrapping CoreOS', cmd)
        if rcode != 0:
            self.logger.critical('Deployment failed: %s' % emsg)
            os.kill(int(os.environ.get('SSH_AGENT_PID')), signal.SIGTERM)
            sys.exit(1)

    def get_subnets(self):
        '''Check the subnet value and split into 2 distincts subnets'''
        svc_pfx = 24
        pods_pfx = 17
        net = netaddr.IPNetwork(self.options['kube_network'])
        pfx_error_msg = (
            "You have to choose a network with a prefix length = 16, "
            "Please use Ansible options if you need to configure a different netmask."
        )
        if net.prefixlen is not 16:
            display.error(pfx_error_msg)
            os.kill(int(os.environ.get('SSH_AGENT_PID')), signal.SIGTERM)
            sys.exit(1)
        subnets = list(net.subnet(pods_pfx))
        pods_network, remaining = subnets[0:2]
        net = netaddr.IPNetwork(remaining)
        svc_network = list(net.subnet(svc_pfx))[0]
        return(svc_network, pods_network)

    def deploy_kubernetes(self):
        '''
        Run the ansible playbook command
        '''
        cmd = [
            playbook_exec, '--ssh-extra-args', '-o StrictHostKeyChecking=no',
            '-e', 'kube_network_plugin=%s' % self.options['network_plugin'],
            '-u',  '%s' % self.options['ansible_user'],
            '-b', '--become-user=root', '-i', self.inventorycfg,
            os.path.join(self.options['kargo_path'], 'cluster.yml')
        ]
        # Configure the network subnets pods and k8s services
        if not validate_cidr(self.options['kube_network'], version=4):
            display.error('Invalid Kubernetes network address')
            os.kill(int(os.environ.get('SSH_AGENT_PID')), signal.SIGTERM)
            sys.exit(1)
        svc_network, pods_network = self.get_subnets()
        # Add any additionnal Ansible option
        if 'ansible_opts' in self.options.keys():
            cmd = cmd + self.options['ansible_opts'].split(' ')
        if 'ansible_opts' in self.options.keys():
            cmd = cmd + self.options['ansible_opts'].split(' ')
        for cloud in ['aws', 'gce']:
            if self.options[cloud]:
                cmd = cmd + ['-e', 'cloud_provider=%s' % cloud]
        if not self.options['coreos']:
            self.check_ping()
        display.display(
            'Kubernetes services network : %s (%s IPs)'
            % (svc_network.cidr, str(svc_network.size.real - 2)),
            color='bright gray'
        )
        display.display(
            'Pods network : %s (%s IPs)'
            % (pods_network.cidr, str(pods_network.size.real - 2)),
            color='bright gray'
        )
        display.display(' '.join(cmd), color='bright blue')
        if not self.options['assume_yes']:
            if not query_yes_no(
                'Run kubernetes cluster deployment with the above command ?'
            ):
                display.display('Aborted', color='red')
                sys.exit(1)
        if self.options['coreos']:
            self.coreos_bootstrap()
            self.check_ping()
            cmd = cmd + ['-e', 'ansible_python_interpreter=/opt/bin/python']
        display.banner('RUN PLAYBOOK')
        self.logger.info(
            'Running kubernetes deployment with the command: %s' % cmd
        )
        rcode, emsg = run_command('Run deployment', cmd)
        if rcode != 0:
            self.logger.critical('Deployment failed: %s' % emsg)
            os.kill(int(os.environ.get('SSH_AGENT_PID')), signal.SIGTERM)
            sys.exit(1)
        display.display('Kubernetes deployed successfuly', color='green')
        os.kill(int(os.environ.get('SSH_AGENT_PID')), signal.SIGTERM)
