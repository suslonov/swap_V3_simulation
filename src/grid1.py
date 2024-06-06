#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Implemented attack:
1)
    swap WETH_in -> token
    mint (token, WETH_additional)
2)
    target swap
3)
    burn (token_out, WETH_out)
    swap token_out -> WETH

"""

import os
os.sys.path.append(os.path.dirname(os.path.abspath('.')))
from web3 import Web3
import numpy as np
import pandas as pd

from _utils.etherscan import _get_abi, _get_contract
from contract_caller import init_context, copy_context
from simulated_attack import simulated_attack1

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

WETH_BUDGET = 200
MULTIPLIER = 10**18  # for attack amount lettice

####################    parameters    ############# 

# # example 2
POOL = "0xc45A81BC23A64eA556ab4CdF08A86B61cdcEEA8b"
tx_block = 19368671
zeroForOne = 1   #!!! don't forget about it !
amount_target = 3319011000000000000
max_attack = 15 # WETH
attack_step = 0.0001
start_attack = attack_step
rounder = len(str(attack_step))

targets = [{"zeroForOne": 1, "amount_target": 3319011000000000000, "amount_min": 0}]

#the second number is the liquidity range width in tick_spacing units
tick_shifts = [(0, 1), (-1, 2)]
####################  end  parameters    ############# 

block = w3.eth.get_block(tx_block - 1)
prev_block_hash = block["hash"].hex()

context = {"w3": w3}
context["pool_address"] = POOL
context["version"] = "uniswap_V3"
context["pool_contract"] = get_contract(w3, POOL)
context["block_hash"] = prev_block_hash

# preload_ticks = int(max([2] + [abs(t[0]) for t in tick_shifts]) * 1.5)
init_context(context, 20) # preload +/- 10 ticks
context0 = copy_context(context)

print("slot0 tick", context["slot0"]["tick"])
results = []
for ts1, ts2 in tick_shifts:
    print("liquidity providing: shift", ts1, "width", ts2)
    amount_a = start_attack
    while amount_a <= max_attack:
        inputs = {"ETH_amount": amount_a,
                  "amount": int(amount_a * MULTIPLIER),
                  "zeroForOne": zeroForOne,
                  "tick_shift1": ts1,
                  "tick_shift2": ts2,
                  "WETH_BUDGET": WETH_BUDGET,
                  }
        contexts = {"pool": copy_context(context0)}
        result = simulated_attack1(inputs, targets, contexts)
        if not result is None:
            results.append(result)
        amount_a = round(amount_a + attack_step, rounder)

df = pd.DataFrame(results)
# df.to_csv("path")
if zeroForOne:
    print(df.loc[df["resultToken0"].idxmax()])
else:
    print(df.loc[df["resultToken1"].idxmax()])
