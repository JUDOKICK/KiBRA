import json
import logging
import os
import re
from collections import OrderedDict
from threading import RLock

CFG_PATH = '/opt/kirale/'
CFG_FILE = CFG_PATH + 'kibra.cfg'
# Default configuration
CFG = {'dongle_name': 'Test', 'dongle_commcred': 'KIRALE'}
# User configuration read from file
CFG_USER = {}

MUTEX = RLock()

DB_ITEMS_TYPE = 0
DB_ITEMS_DEF = 1
DB_ITEMS_VALID = 2
DB_ITEMS_WRITE = 3
DB_ITEMS_PERS = 4
# TODO: change DB_ITEMS_WRITE for a callback to be used after changing the value
DB_ITEMS = {
    'action_coapserver': [str, None, lambda x: True, True, False],
    'action_dhcp': [str, None, lambda x: True, True, False],
    'action_diags': [str, None, lambda x: True, True, False],
    'action_dns': [str, None, lambda x: True, True, False],
    'action_mdns': [str, None, lambda x: True, True, False],
    'action_nat': [str, None, lambda x: True, True, False],
    'action_network': [str, None, lambda x: True, True, False],
    'action_serial': [str, None, lambda x: True, True, False],
    'all_domain_bbrs': [str, None, lambda x: True, True, False],
    'all_network_bbrs': [str, None, lambda x: True, True, False],
    'autostart': [int, 0, lambda x: x in (0, 1), True, False],
    'bagent_at': [str, None, lambda x: True, False, False],
    'bagent_cm': [int, None, lambda x: True, False, False],
    'bagent_port': [int, None, lambda x: True, False, False],
    'bbr_port': [int, 5683, lambda x: x >= 0 and x < 0xffff, False, False],
    'bbr_seq': [int, 0, lambda x: x >= 0 and x < 0xff, False, True],
    'bbr_status': [str, None, lambda x: True, False, False],
    'bridging_mark': [int, None, lambda x: True, False, False],
    'bridging_table': [str, None, lambda x: True, False, False],
    'dhcp_pool': [str, None, lambda x: True, False, False],
    'dongle_channel': [int, None, lambda x: True, True, False],
    'dongle_clear': [int, None, lambda x: True, True, False],
    'dongle_commcred': [str, None, lambda x: True, True, True],
    'dongle_eid': [str, None, lambda x: True, False, False],
    'dongle_emac': [str, None, lambda x: True, True, False],
    'dongle_ll': [str, None, lambda x: True, False, False],
    'dongle_mac': [str, None, lambda x: True, False, False],
    'dongle_name': [str, None, lambda x: True, True, True],
    'dongle_netkey': [str, None, lambda x: True, True, False],
    'dongle_netname': [str, None, lambda x: True, True, False],
    'dongle_outband': [str, None, lambda x: True, True, False],
    'dongle_panid': [str, None, lambda x: True, True, False],
    'dongle_prefix': [str, None, lambda x: True, True, False],
    'dongle_rloc': [str, None, lambda x: True, False, False],
    'dongle_role': [str, None, lambda x: True, True, False],
    'dongle_serial': [str, None, lambda x: True, False, True],
    'dongle_sjitter': [str, None, lambda x: True, True, True],
    'dongle_status': [str, None, lambda x: True, False, False],
    'dongle_xpanid': [str, None, lambda x: True, True, False],
    'dua_prefix': [str, None, lambda x: True, True, False],
    'exterior_ifname': [str, None, lambda x: True, False, False],
    'exterior_ifnumber': [int, None, lambda x: True, False, False],
    'exterior_ipv4': [str, None, lambda x: True, False, False],
    'exterior_port_mc': [int, None, lambda x: True, False, False],
    'interior_ifname': [str, None, lambda x: True, False, False],
    'interior_ifnumber': [int, None, lambda x: True, False, False],
    'interior_mac': [str, None, lambda x: True, False, False],
    'maddrs_perm': [str, None, lambda x: True, False, False],
    'mcast_admin_fwd': [int, 1, lambda x: x in (0, 1), False, False],
    'mcast_out_fwd': [int, 1, lambda x: x in (0, 1), False, False],
    'mlr_timeout': [int, 3600, lambda x: x >= 300 and x < 0xffffffff, True, True],
    'pool4': [str, None, lambda x: True, False, False],
    'prefix': [str, None, lambda x: True, False, False],
    'rereg_delay': [int, 5, lambda x: x >= 1 and x < 0xffff, True, True],
    'serial_device': [str, None, lambda x: True, False, False],
    'status_coapserver': [str, None, lambda x: True, False, False],
    'status_dhcp': [str, None, lambda x: True, False, False],
    'status_diags': [str, None, lambda x: True, False, False],
    'status_dns': [str, None, lambda x: True, False, False],
    'status_mdns': [str, None, lambda x: True, False, False],
    'status_nat': [str, None, lambda x: True, False, False],
    'status_network': [str, None, lambda x: True, False, False],
    'status_serial': [str, None, lambda x: True, False, False],
}


def modifiable_keys():
    return [x for x in DB_ITEMS.keys() if DB_ITEMS[x][DB_ITEMS_WRITE]]


def get(key):
    if not key in DB_ITEMS.keys():
        raise Exception('Trying to use a non existing DB entry key (%s).' % key)
    with MUTEX:
        if key not in CFG:
            return None
        else:
            value = CFG[key]
            if DB_ITEMS[key][DB_ITEMS_TYPE] is int:
                return int(value)
            return value


def set(key, value):
    value = str(value)
    with MUTEX:
        # Only save if value has changed
        if key not in CFG or CFG[key] is not value:
            CFG[key] = value
            logging.debug('Saving %s as %s.', key, value)


def delete(key):
    '''Delete the database element if it exists'''
    try:
        del CFG[key]
    except KeyError:
        pass


def has_keys(key_list):
    ''' Return True if all keys exist in CFG'''
    with MUTEX:
        for key in key_list:
            if key not in CFG:
                return False
    return True


def load():
    global CFG, CFG_USER
    with MUTEX:
        if os.path.isfile(CFG_FILE):
            logging.debug('Loading configuration file %s', CFG_FILE)
            with open(CFG_FILE, 'r') as json_db:
                CFG = json.load(json_db)
            CFG_USER = CFG.copy()
        else:
            logging.debug('Using default configuration.')
            os.makedirs(CFG_PATH, exist_ok=True)
            with open(CFG_FILE, 'w') as json_db:
                json.dump(CFG, json_db)


def dump():
    logging.debug('Exporting configuration')
    config = json.dumps(OrderedDict(sorted(CFG.items())), indent=2)
    return config


def save():
    '''Save persistent configuration information'''
    with MUTEX:
        config = CFG_USER
        # Collect persistent values
        for key in DB_ITEMS.keys():
            if DB_ITEMS[key][DB_ITEMS_PERS]:
                config[key] = CFG[key]
        if os.path.isfile(CFG_FILE):
            logging.debug('Saving configuration file %s', CFG_FILE)
            config = json.dumps(OrderedDict(sorted(config.items())), indent=2)
            with open(CFG_FILE, 'w') as file_:
                file_.write(config + '\n')


def find_in_file(file, prev_patt, follow_patt):
    ''' For a given file, find a text between two patterns'''
    if os.path.isfile(file):
        with open(file, 'r') as file_:
            data = file_.read()
            result = re.search(r'%s(.*)%s' % (prev_patt, follow_patt), data)
            if result != None:
                return result.group(1)


def del_from_file(file, start_patt, end_patt):
    ''' For a given file, remove a text between two patterns,
    including the patterns'''
    if os.path.isfile(file):
        with open(file, 'r+') as file_:
            data = file_.read()
            data = re.sub(
                r'%s(.*?)%s' % (start_patt, end_patt),
                '',
                data,
                flags=re.DOTALL)
            file_.seek(0)
            file_.truncate()
            file_.write(data)
