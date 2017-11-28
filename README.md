Kubespray wrapper
=============

This tool helps to deploy a kubernetes cluster with ansible.


Example on GCE:
[![asciicast](https://asciinema.org/a/065mhh5pzmxcwxgp6evebarvd.png)](https://asciinema.org/a/065mhh5pzmxcwxgp6evebarvd?speed=4)

Requirements
============

-   **Ansible v2.3 (or newer)**
-   The current user must have its ssh **public key** installed on the
    remote servers.
-   The remote user (option --user) must be in the sudoers with no
    password

Installation
============

### Python pip

    sudo pip2 install kubespray


Config file
-----------

A config file can be updated (yaml). (default: *~/.kubespray.yml* ) </br>
This file contains default values for some parameters that don't change
frequently </br>
**Note** these values are **overwritten** by the command line.


    # Common options
    # ---------------
    # Path where the kubespray ansible playbooks will be installed
    # Defaults to current user's home directory if not set
    # kubespray_path: "/tmp"
    # Default inventory path
    kubespray_git_repo: "https://github.com/kubernetes-incubator/kubespray.git"
    # Logging options
    loglevel: "info"

    # Amazon web services options
    # ---
    # aws_access_key: "<key>"
    # aws_secret_key: "<secret_key>"
    # key_name: "<keypair_name>"
    # ami: "<aws_ami>"
    # masters_instance_type: "<masters_instance_type>"
    # nodes_instance_type: "<nodes_instance_type>"
    # etcds_instance_type: "<etcds_instance_type>"
    # masters_instance_profile_name: "<master_instance_profile_name>"
    # nodes_instance_profile_name: "<nodes_instance_profile_name>"
    # etcds_instance_profile_name: "<etcds_instance_profile_name>"
    # security_group_name: "<security_group_name>"
    # security_group_id: "<security_group_id>"
    # assign_public_ip: True
    # vpc_subnet_id: "<vpc_id>"
    # region: "<aws_region>"
    # tags:
    #   - type: k8s

    # OpenStack options
    # ---
    # os_auth_url: "https://"
    # os_username: "k8s"
    # os_password: "secret"
    # os_project_name: "k8s"
    # masters_flavor: "m1.small"
    # nodes_flavor: "m1.small"
    # etcds_flavor: "m1.small"
    # image: "wily-server-cloudimg-amd64"
    # network: "my-network"
    # sshkey: "my-pub-key"
    ...

Basic usage
-----------
**Note**: You may want to choose the architecture of your cluster. </br>
Here are 3 examples:
* 3 vms, all 3 have etcd installed, all 3 are nodes (running pods), 2 of them run master components
```
kubespray [prepare|aws|gce] --nodes 3
```

![3nodes](https://s32.postimg.org/8q7gns8ut/3nodes.png)
* 6 vms, 2 are nodes and masters, 1 is node only and a distinct etcd cluster
```
kubespray [prepare|aws|gce] --nodes 3 --etcds 3
```

![3nodes3etcds](https://s32.postimg.org/hphgxcjmt/3nodes_3etcds.png)
* 8 vms, 2 distinct masters, 3 nodes and 3 etcds
```
kubespray [prepare|aws|gce] --nodes 3 --etcds 3 --masters 2
```

![3nodes3etcds2masters](https://s31.postimg.org/h4gdu4qjv/3nodes_2masters_3etcds.png)

You should have at least 3 nodes but you can spawn only one instance for
tests purposes.

### Generate inventory for a baremetal cluster

If the servers are already available you can use the argument **prepare**
The command below will just clone the git repository and creates the
inventory.
The hostvars must be separated by a **comma without spaces**

    kubespray prepare --nodes node1[ansible_ssh_host=10.99.21.1] node2[ansible_ssh_host=10.99.21.2] node3[ansible_ssh_host=10.99.21.3] [--etcds N+] [--masters N+]

### Run instances and generate the inventory on Clouds


**AWS**

In order to create vms on AWS you can either edit the config file *~/.kubespray.yml* or set the options with the argument **aws**
if the config file is filled with the proper information you just need to run the following command

    kubespray aws --nodes 3 [--etcds N+] [--masters N+] [--nodes-instance-type m4.large]

Another example which download kubespray's repo in a defined directory and set the cluster name

    kubespray aws --nodes 3 -p /tmp/mykubespray --cluster-name foobar


**GCE**

In order to create vms on GCE you can either edit the config file */etc/kubespray/kubespray.yml* or set the options with the argument **gce**
if the config file is filled with the proper information you just need to run the following command

    kubespray gce --nodes 3

Another example if you already have a kubespray repository in your home dir

    kubespray gce --nodes 3 --noclone --cluster-name foobar [--nodes-machine-type n1-standard-4]


**OpenStack**

In order to create vms on a OpenStack cluster you can either edit the config file *~/.kubespray.yml* or set the options with the argument **openstack**.
The options **network** and **sshkey** are required and need to be created before running kubespray, you can either create them using the OpenStack Dashboard or the OpenStack CLI clients. Running the ansible routines that kubespray will invoke requires to have installed the [openstack cli tools](http://docs.openstack.org/user-guide/common/cli_install_openstack_command_line_clients.html) and openstack [shade](http://docs.openstack.org/infra/shade/installation.html).


Create a network using the OpenStack Neutron client

    # create network
    $ neutron net-create k8s-network

    Created a new network:
    +-----------------+--------------------------------------+
    | Field           | Value                                |
    +-----------------+--------------------------------------+
    | admin_state_up  | True                                 |
    | id              | 18989cb2-d9fc-4abd-85e8-fe5b33df3541 |
    | mtu             | 0                                    |
    | name            | k8s-network                          |
    | router:external | False                                |
    | shared          | False                                |
    | status          | ACTIVE                               |
    | subnets         |                                      |
    | tenant_id       | 5de2cf232a674b05983b61fdc1ea67aa     |
    +-----------------+--------------------------------------+

    # create subnet
    $ neutron subnet-create --name k8s-subnet --dns-nameserver 8.8.8.8 --enable-dhcp --allocation_pool "start=192.168.0.100,end=192.168.0.200" k8s-network 192.168.0.0/24

    Created a new subnet:
    +-------------------+----------------------------------------------------+
    | Field             | Value                                              |
    +-------------------+----------------------------------------------------+
    | allocation_pools  | {"start": "192.168.0.100", "end": "192.168.0.200"} |
    | cidr              | 192.168.0.0/24                                     |
    | dns_nameservers   |                                                    |
    | enable_dhcp       | True                                               |
    | gateway_ip        | 192.168.0.1                                        |
    | host_routes       |                                                    |
    | id                | fc5a5436-de3a-4d68-9846-d977d047d6d7               |
    | ip_version        | 4                                                  |
    | ipv6_address_mode |                                                    |
    | ipv6_ra_mode      |                                                    |
    | name              | k8s-subnet                                         |
    | network_id        | 18989cb2-d9fc-4abd-85e8-fe5b33df3541               |
    | subnetpool_id     |                                                    |
    | tenant_id         | 5de2cf232a674b05983b61fdc1ea67aa                   |
    +-------------------+----------------------------------------------------+

    # create a router
    $ neutron router-create k8s-router

    Created a new router:
    +-----------------------+--------------------------------------+
    | Field                 | Value                                |
    +-----------------------+--------------------------------------+
    | admin_state_up        | True                                 |
    | external_gateway_info |                                      |
    | id                    | 69027fa4-239b-4bae-89bc-3040c365ee4d |
    | name                  | k8s-router                           |
    | routes                |                                      |
    | status                | ACTIVE                               |
    | tenant_id             | 5de2cf232a674b05983b61fdc1ea67aa     |
    +-----------------------+--------------------------------------+

    # set gateway network, external_network is the name of the external network defined by your OpenStack provider
    $ neutron router-gateway-set k8s-router external_network

    Set gateway for router k8s-router

    # add k8s-subnet to k8s-router, plug the virtual cable
    $ neutron router-interface-add k8s-router subnet=k8s-subnet

    Added interface a62ca3b4-3302-45b6-803e-f87a4f43b4b6 to router k8s-router.

Upload a ssh key in order to connect to the vms using the OpenStack Nova client


    # import SSH Public Key with name k8s-pub-key
    $ nova keypair-add --pub-key id_rsa.pub k8s-pub-key


Once the preparation have been completed you can enter the required options to the config file */etc/kubespray/kubespray.yml*:

    ...

    network: "k8s-network"
    sshkey: "k8s-pub-key"

    ...


If the config file is filled with the proper information you just need to run the following command

    kubespray openstack --masters 2 --nodes 2 --etcds 3

Another example if you already have a kubespray repository in your home dir

    kubespray openstack --masters 2 --nodes 2 --etcds 3 --noclone --cluster-name foobar


**Add a node to an existing cluster**
It's possible to add nodes to a running cluster, </br>
these newly added nodes will act as node only (no etcd, no master components)

Add a node

    kubespray [aws|gce] --add --nodes 1

Then deploy the cluster with the same options as the running cluster.


### Deploy cluster

The last step is to run the cluster deployment.

**Note**:
-   default network plugin : flannel (vxlan) default
-   default kubespray\_path : "/home/\<current\_user\>/kubespray"
-   inventory path : "\<kubespray\_path\>/inventory/inventory.cfg".
-   The option `--inventory` allows to use an existing inventory (file or dynamic)
-   On coreos (--coreos) the directory **/opt/bin** must be writable
- You can use all Ansible's variables with
`--ansible-opts '-e foo=bar -e titi=toto -vvv'` (the value must be enclosed by simple quotes)

some examples:

Deploy with the default options on baremetal

    kubespray deploy

Deploy on AWS using a specific kubespray directory and set the api password

    kubespray deploy --aws --passwd secret -p /tmp/mykubespray -n weave

Deploy a kubernetes cluster on CoreOS servers located on GCE

    kubespray deploy -u core -p /kubespray-dc1 --gce --coreos --cluster-name mykube --kube-network 10.42.0.0/16
