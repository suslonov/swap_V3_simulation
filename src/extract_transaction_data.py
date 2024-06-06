#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
os.sys.path.append(os.path.dirname(os.path.abspath('.')))
from web3 import Web3
import eth_abi

from _utils.etherscan import _get_abi, _get_contract


HEADERS_E = {'Content-Type': "application/json"}
ETHERSCAN_GETABI = 'http://api.etherscan.io/api?module=contract&action=getabi&address={}&apikey={}'

KEY_FILE = '../keys/alchemy.sec'
ETHERSCAN_KEY_FILE = '../keys/etherscan.sec'

with open(KEY_FILE, 'r') as f:
    k1 = f.readline()
    ALCHEMY_URL = k1.strip('\n')
    k2 = f.readline()
    ALCHEMY_WSS = k2.strip('\n')

with open(ETHERSCAN_KEY_FILE, 'r') as f:
    k1 = f.readline()
    ETHERSCAN_KEY = k1.strip('\n')

def get_contract(w3, address, abi_type="pool"):
    abi = _get_abi(address, ETHERSCAN_KEY, abi_type=abi_type)
    return _get_contract(w3, abi, Web3.to_checksum_address(address))


w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

tx_hash = "0xe3447e3a7a1fe064ac5e66f3c2cce5e05d9f7f5b1492cb58a61a6a6cedee5738"
to_address_router = "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"

tx = w3.eth.get_transaction(tx_hash)
contract = get_contract(w3, to_address_router, None)

decoded_input = contract.decode_function_input(tx["input"])

for c in decoded_input[1]["commands"]:
    print(c)

UNISWAP_UNIVERSAL_ROUTER_COMMANDS = [
    ("V3_SWAP_EXACT_IN", 0x00, ["address", "uint256", "uint256", "bytes", "bool"]),
    ("V3_SWAP_EXACT_OUT", 0x01, ["address", "uint256", "uint256", "bytes", "bool"]),
    ("SWEEP", 0x04, ["address", "address", "uint256"]),
    ("TRANSFER", 0x05, ["address", "address", "uint256"]),
    ("V2_SWAP_EXACT_IN", 0x08, ["address", "uint256", "uint256", "address[]", "bool"]),
    ("V2_SWAP_EXACT_OUT", 0x09, ["address", "uint256", "uint256", "address[]", "bool"]),
    ("WRAP_ETH", 0x0b),
    ("UNWRAP_WETH", 0x0c),
    ]

abi = UNISWAP_UNIVERSAL_ROUTER_COMMANDS[5][2]
command_input = eth_abi.abi.decode(abi, decoded_input[1]["inputs"][1])
print(command_input[:3])
print(command_input[3].hex())

   