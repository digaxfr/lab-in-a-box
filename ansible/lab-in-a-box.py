#!/usr/bin/env python3

'''
Dynamically generate inventory for lab-in-a-box. What ends up happening is really reading in yaml dictionary that defines our lab layout. The output of it will be a more complete inventory.

Used ec2.py as a reference: https://github.com/ansible/ansible/blob/devel/contrib/inventory/ec2.py
'''

import json
import netaddr
import yaml

class LabInABox(object):

    def _empty_inventory(self):
        return { '_meta': { 'hostvars': {} } }

    def _empty_group(self):
        return { 'hosts': [], 'vars': {}, 'children': [] }

    def _set_all_groupvars(self):
        details = self._empty_group()
        details['vars'] = {
            'domain_name': DOMAIN_NAME,
            'mac_prefix': MAC_PREFIX,
            'public_ssh_key': PUBLIC_SSH_KEY,
        }
        return details

    def _set_host_system_groupvars(self):

        ''' Assumes localhost. '''

        details = self._empty_group()
        details['hosts'].append('localhost')

        return details

    def _set_host_system_hostvars(self, config):

        ''' Assumes localhost. '''

        details = {
            'ansible_connection': 'local',
            'bgp_asn': HOST_BGP_ASN
        }

        # Create the list of lab networks and routing networks
        details['networks'] = {}
        for network, network_details in config.items():
            ip_peering_network = netaddr.IPNetwork(network_details['peering_network'])
            ip_network = netaddr.IPNetwork(network_details['network'])
            details['networks'][network] = {
                'name': network,
                'network': str(ip_network.network),
                'network_cidr': str(ip_network.cidr),
                'network_ext': str(ip_peering_network.network),
                'network_ext_cidr': str(ip_peering_network.cidr)
            }
            details['networks']['routing-%s' % network] = {
                'ip': str(ip_peering_network[0]),
                'ip_cidr': str('%s/%s' % (ip_peering_network[0], ip_peering_network.prefixlen)),
                'name': 'routing-%s' % network,
                'netmask': str(ip_peering_network.netmask),
                'netmask_int': str(ip_network.netmask),
                'network': str(ip_peering_network.network),
                'network_cidr': str(ip_peering_network.cidr),
                'network_int': str(ip_network.network),
                'network_int_cidr': str(ip_network.cidr)
            }
        return details

    def _set_lab_net_groupvars(self, network_name, network_details):

        '''
        Set the groupvars for a lab network.
        '''

        details = self._empty_group()

        # Add the router
        details['hosts'].append('router-%s.%s' % (network_name, DOMAIN_NAME))

        # Add each machine
        for machine in network_details['machines']:
            details['hosts'].append('%s.%s' % (machine, DOMAIN_NAME))

        # Add various vars
        ip_network = netaddr.IPNetwork(network_details['network'])
        ip_peering_network = netaddr.IPNetwork(network_details['peering_network'])
        details['vars']['bgp_asn'] = network_details['bgp_asn']
        details['vars']['bgp_asn_uplink'] = HOST_BGP_ASN
        details['vars']['bgp_peering_network_cidr'] = str(ip_peering_network.cidr)
        details['vars']['bgp_uplink_peer'] = str(ip_peering_network[0])
        details['vars']['dhcp_relay_server'] = str(ip_peering_network[0])
        details['vars']['network_cidr'] = str(ip_network.cidr)
        details['vars']['network_name'] = network_name

        return details

    def _set_machine_hostvars(self, machine_name, network_name, network_details):

        '''
        Set the hostvars for machines.
        Some constraints to know:
        - Support for one virtual disk at the moment
        - Support for one NIC at the moment
        '''

        details = {}

        # Get the base set of attributes
        for machine_attribute, machine_value in network_details['machines'][machine_name].items():
            details[machine_attribute] = machine_value

        # Add any additions now
        ip_network = netaddr.IPNetwork(network_details['network'])
        details['gateway'] = str(ip_network[1])
        details['ip_cidr'] = str('%s/%s' % (ip_network.ip, ip_network.prefixlen))
        details['netmask'] = str(ip_network.netmask)
        details['network_cidr'] = str(ip_network.cidr)
        details['network_name'] = network_name

        return details

    def _set_router_hostvars(self, network_name, network_details):

        '''
        Set the hostvars for routers.
        Some constraints/assumptions to know:
        - Support for one virtual disk
        - Hard coded to two NICs
            - ip = Uplink to hypervisor
            - *_int = Downlink to lab subnet
        - Router networking info will override those of the group (lab-N) due to poor design... whatever, there's always a v2 in the future
        '''

        details = {}
        details['cpu'] = 1
        details['memory'] = 384
        details['disks'] = [{ 'name': 'vda', 'size': 8 }]
        details['type'] = 'router'
        ip_network = netaddr.IPNetwork(network_details['peering_network'])
        ip_int_network = netaddr.IPNetwork(network_details['network'])
        details['gateway'] = str(ip_network[0])
        details['ip'] = str(ip_network[1])
        details['ip_cidr'] = '%s/%s' % (ip_network[1], ip_network.prefixlen)
        details['ip_int'] = str(ip_int_network[1])
        details['ip_int_cidr'] = '%s/%s' % (ip_int_network[1], ip_int_network.prefixlen)
        details['netmask'] = str(ip_network.netmask)
        details['netmask_int'] = str(ip_int_network.netmask)
        details['network_cidr'] = str(ip_network.cidr)
        details['network_int_cidr'] = str(ip_int_network.cidr)
        details['network_int_name'] = network_name
        details['network_name'] = 'routing-%s' % network_name
        return details

    def _default_vars(self):

        ''' Set variables that would be used globally. '''

        with open('lab-in-a-box.yaml', 'r') as stream:
            try:
                config = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print('Error opening yaml:', exc)

        global DOMAIN_NAME, HOST_BGP_ASN, MAC_PREFIX, PUBLIC_SSH_KEY
        DOMAIN_NAME = config['lab_domain_name']
        HOST_BGP_ASN = config['lab_host_bgp_asn']
        MAC_PREFIX = config['lab_mac_prefix']
        PUBLIC_SSH_KEY = config['lab_public_ssh_key']

    def __init__(self):

        # Initialize empty inventory
        self.inventory = self._empty_inventory()
        self._default_vars()

        # Load up our yaml
        with open('lab-in-a-box.yaml', 'r') as stream:
            try:
                config = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print('Error opening yaml:', exc)

        # For the first iteration of this script, we will take a very easy-to-read approach; meaning it will not be efficient

        # Create the all group and set groupvars
        self.inventory['all'] = self._set_all_groupvars()

        # Generate the host system group and hostvars
        self.inventory['host_system'] = self._set_host_system_groupvars()
        self.inventory['_meta']['hostvars']['localhost'] = self._set_host_system_hostvars(config['lab_machines'])

        # Generate lab network groups
        for net_group, net_details in config['lab_machines'].items():
            self.inventory[net_group] = self._set_lab_net_groupvars(net_group, net_details)

        # Generate auxiliary groups
        self.inventory['routers'] = self._empty_group()
        for net_group in config['lab_machines']:
            self.inventory['routers']['hosts'].append('router-%s.%s' % (net_group, DOMAIN_NAME))
        self.inventory['dhcrelay'] = self._empty_group()
        self.inventory['dhcrelay']['children'].append('routers')

        # ESXi
        self.inventory['esxi'] = self._empty_group()
        for _, net_details in config['lab_machines'].items():
            for machine, machine_details in net_details['machines'].items():
                if machine_details['type'] == 'esxi':
                    self.inventory['esxi']['hosts'].append('%s.%s' % (machine, DOMAIN_NAME))

        # machines
        self.inventory['machines'] = self._empty_group()
        for _, net_details in config['lab_machines'].items():
            for machine, machine_details in net_details['machines'].items():
                if machine_details['type'] == 'machine':
                    self.inventory['machines']['hosts'].append('%s.%s' % (machine, DOMAIN_NAME))

        # Generate machine hosts
        for net_group, net_details in config['lab_machines'].items():
            for machine, machine_details in net_details['machines'].items():
                hostname = '%s.%s' % (machine, DOMAIN_NAME)
                self.inventory['_meta']['hostvars'][hostname] = self._set_machine_hostvars(machine, net_group, net_details)

        # Generate router hosts
        for net_group, net_details in config['lab_machines'].items():
            router = 'router-%s.%s' % (net_group, DOMAIN_NAME)
            self.inventory['_meta']['hostvars'][router] = self._set_router_hostvars(net_group, net_details)

        print(json.dumps(self.inventory))

if __name__ == '__main__':
    LabInABox()
