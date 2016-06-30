#!/usr/bin/env python
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

import logging
import shutil
import requests
import random
import os
import re
import netaddr
import sys
import string
import getpass
from ansible.utils.display import Display
from subprocess import PIPE, STDOUT, Popen, CalledProcessError
display = Display()


def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None


def read_password():
    pw = getpass.getpass(prompt="API 'kube' password: ")
    if len(pw) < 6:
        display.warning('Password is too short')
    pw2 = getpass.getpass(prompt="Confirm password: ")
    if pw != pw2:
        display.error("Passwords don't match")
        sys.exit(1)
    return(pw)


def remove_duplicates(seq):
   noDupes = []
   [noDupes.append(i) for i in seq if not noDupes.count(i)]
   return noDupes


def query_yes_no(question, default="yes"):
    """Question user input 'Yes' or 'No'"""
    valid = {"yes": True, "y": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("Invalid default answer: '%s'" % default)
    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write(
                "Please answer with 'yes' or 'no' (or 'y' or 'n').\n"
            )


def get_logger(logfile, loglevel):
    logger = logging.getLogger()
    handler = logging.FileHandler(logfile)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, loglevel.upper()))
    return logger


def get_cluster_name():
    try:
        word_site = "http://svnweb.freebsd.org/csrg/share/dict/words?view=co&content-type=text/plain"
        response = requests.get(word_site)
        words = response.content.splitlines()
        cluster_name = random.choice(words).decode("utf-8")
    except:
        cluster_name = id_generator()
    if not re.match('^(?:[a-z](?:[-a-z0-9]{0,61}[a-z0-9])?)$', cluster_name):
        get_cluster_name()
    return(cluster_name.lower())


def clone_kargo_git_repo(options):
    if not options['add_node']:
        if (os.path.isdir(options['kargo_path']) and not options['assume_yes']
                and not options['noclone']):
            display.warning(
                'A directory %s already exists' % options['kargo_path']
            )
            if not query_yes_no(
                    'Are you sure to overwrite it ?'
            ):
                    display.display('Aborted', color='red')
                    sys.exit(1)
        if not options['noclone']:
            clone_git_repo(
                'kargo', options['kargo_path'], options['kargo_git_repo']
            )


def clone_git_repo(name, directory, git_repo):
    if which('git') is None:
        display.error('Cannot find git binary! check your installation')
        sys.exit(1)
    if os.path.isdir(directory):
        shutil.rmtree(directory)
    display.banner('CLONING %s GIT REPO' % name.upper())
    cmd = ["git", "clone", git_repo, directory]
    rcode, emsg = run_command('Clone kargo repository from github', cmd)
    if rcode != 0:
        display.error('Cannot clone kargo repository from github')
        sys.exit(1)
    display.display('%s repo cloned' % name, color='green')


def run_command(description, cmd):
    '''
    Execute a system command
    '''
    try:
        proc = Popen(
            cmd, stdout=PIPE, stderr=STDOUT,
            universal_newlines=True, shell=False
        )
        with proc.stdout:
            for line in iter(proc.stdout.readline, b''):
                print(line),
        proc.wait()
        return(proc.returncode, None)
    except CalledProcessError as e:
        display.error('%s: %s' % (description, e.output))
        emsg = e.message
        return(proc.returncode, emsg)


def id_generator(size=6, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def validate_cidr(cidr, version):
    """
    Validates that a CIDR is valid. Returns true if valid, false if
    not. Version can be "4", "6", None for "IPv4", "IPv6", or "either"
    respectively.
    """
    try:
        ip = netaddr.IPNetwork(cidr, version=version)
        return True
    except (netaddr.core.AddrFormatError, ValueError, TypeError):
        return False
