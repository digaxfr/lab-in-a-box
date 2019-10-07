import netaddr

def liab_machine_list(arg):
    """ Return a list of machines """
    machine_list = []
    for network, net_props in arg.items():
        for machine, machine_props in net_props['machines'].items():
            new_machine = machine_props
            new_machine['name'] = machine
            new_machine['network_name'] = network
            machine_list.append(new_machine)
    return machine_list

def liab_router_list(arg):
    """ Return a list of routers """
    router_list = []
    for network, net_props in arg.items():
        """ Router's IP is always the second/upper IP in the peering network """
        ipnet_prefix = netaddr.IPNetwork(net_props['peering_network'])
        new_router = {
            'name': "router-%s" % network,
            'cpu': 1,
            'memory': 512,
            'ip': "%s" % ipnet_prefix[1],
            'disks': [
                { 'name': "vda", 'size': "8" }
            ],
            'network_name': network,
            'bgp_asn': net_props['bgp_asn'],
        }
        router_list.append(new_router)
    return router_list

class FilterModule(object):
    """ Lab-in-a-Box manipulation filters """
    filter_map = {
        'liab_machine_list' : liab_machine_list,
        'liab_router_list' : liab_router_list,
    }

    def filters(self):
        return self.filter_map
