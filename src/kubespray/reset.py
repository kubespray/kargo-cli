import re
import sys
import os
import yaml
import signal
import netaddr
from subprocess import PIPE, STDOUT, Popen, check_output, CalledProcessError
from kubespray.common import get_logger, query_yes_no, run_command, which, validate_cidr
from ansible.utils.display import Display
display = Display()
playbook_exec = which('ansible-playbook')
ansible_exec = which('ansible')

class RunResetPlaybook(object):
    '''
    Run the Ansible playbook to reset the kubernetes cluster
    '''
    def __init__(self, options):
        self.existing_ssh_agent = False
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

    def kill_ssh_agent(self):
        if self.existing_ssh_agent:
            return

        if 'SSH_AGENT_PID' in os.environ:
            agent_pid = os.environ.get('SSH_AGENT_PID')

            if agent_pid.isdigit():
                os.kill(int(agent_pid), signal.SIGTERM)

    def ssh_prepare(self):
        '''
        Run ssh-agent and store identities
        '''

        if 'SSH_AUTH_SOCK' in os.environ:
            self.existing_ssh_agent = True
            self.logger.info('Using existing ssh agent')
            return

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
        except IOError:
            display.error('Could not find SSH key. Have you run ssh-keygen?')
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
            self.kill_ssh_agent()
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
        if 'sshkey' in self.options.keys():
            cmd = cmd + ['--private-key', self.options['sshkey']]
        if self.options['ask_become_pass']:
            cmd = cmd + ['--ask-become-pass']
        if self.options['coreos']:
            cmd = cmd + ['-e', 'ansible_python_interpreter=/opt/bin/python']
        display.display(' '.join(cmd))
        rcode, emsg = run_command('SSH ping hosts', cmd)
        if rcode != 0:
            self.logger.critical('Cannot connect to hosts: %s' % emsg)
            self.kill_ssh_agent()
            sys.exit(1)
        display.display('All hosts are reachable', color='green')

    def reset_kubernetes(self):
        '''
        Run reset the ansible playbook command
        '''
        cmd = [
            playbook_exec, '--ssh-extra-args', '-o StrictHostKeyChecking=no',
            '-u',  '%s' % self.options['ansible_user'],
            '-b', '--become-user=root', '-i', self.inventorycfg,
            os.path.join(self.options['kubespray_path'], 'reset.yml')
        ]
        # Ansible verbose mode
        if 'verbose' in self.options.keys() and self.options['verbose']:
            cmd = cmd + ['-vvvv']
        # Add privilege escalation password
        if self.options['ask_become_pass']:
            cmd = cmd + ['--ask-become-pass']
        # Add any additionnal Ansible option
        if 'ansible_opts' in self.options.keys():
            cmd = cmd + self.options['ansible_opts'].split(' ')
        self.check_ping()

        if not self.options['assume_yes']:
            if not query_yes_no(
                'Reset kubernetes cluster with the above command ?'
            ):
                apply=no
                display.display('Aborted', color='red')
                sys.exit(1)
        display.banner('RUN Reset PLAYBOOK')
        cmd = cmd + ['--extra-vars','reset_confirmation=yes']
        self.logger.info(
            'Running kubernetes reset with the command: %s' % ' '.join(cmd)
        )
        cmd = cmd + ['--extra-vars','reset_confirmation=yes']
        rcode, emsg = run_command('Reset deployment', cmd)
        if rcode != 0:
            self.logger.critical('Reset failed: %s' % emsg)
            self.kill_ssh_agent()
            sys.exit(1)
        display.display('Kubernetes Reset successfuly', color='green')
        self.kill_ssh_agent()
