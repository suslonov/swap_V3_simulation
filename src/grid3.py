#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Implemented attack:
1)
    swap WETH_in -> token
    swap WETH_in2 -> token (V3  -- two only ! )
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
from simulated_attack import simulated_attack3
from contract_caller import zero_for_one_weth

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

token = "0xb23d80f5FefcDDaa212212F028021B41DEd428CF"
zeroForOne = zero_for_one_weth(token)

pool1 = "0x16588709ca8f7B84829B43cC1c5cb7e84a321b16"
max_attack1 = 20 # WETH
attack_step1 = 0.01
start_attack1 = attack_step1
rounder1 = len(str(attack_step1))

pool2 = "0xCD423F3ab39a11ff1D9208B7D37dF56E902C932B"
# zeroForOne the same
max_attack2 = 10 # WETH
attack_step2 = 0.01
start_attack2 = attack_step2
rounder2 = len(str(attack_step2))

tx_block = 19495913
block = w3.eth.get_block(tx_block - 1)
prev_block_hash = block["hash"].hex()

context1 = {"w3": w3}
context1["version"] = "uniswap_V3"
context1["pool_address"] = pool1
context1["pool_contract"] = get_contract(w3, pool1)
context1["block_hash"] = prev_block_hash
init_context(context1, 20) # preload +/- 10 ticks
context01 = copy_context(context1)

context2 = {"w3": w3}
context2["version"] = "uniswap_V3"
context2["pool_address"] = pool2
context2["pool_contract"] = get_contract(w3, pool2, abi_type="pool")
context2["block_hash"] = prev_block_hash
init_context(context2, 20) # preload +/- 10 ticks
context02 = copy_context(context2)

targets = [{"zeroForOne": 0, "amount_target": 26597374021829455877, "amount_min": 0}]

#the second number is the liquidity range width in tick_spacing units
tick_shifts = [(0, 1), (1, 1), (-1, 2)]

####################  end  parameters    ############# 


print("slot0 tick", context1["slot0"]["tick"])
results = []
for ts1, ts2 in tick_shifts:
    print("liquidity providing: shift", ts1, "width", ts2)
    amount_a1 = start_attack1
    while amount_a1 <= max_attack1:
        amount_a2 = start_attack2
        while amount_a2 <= max_attack2:
            inputs = {"ETH_amount1": amount_a1,
                      "amount1": int(amount_a1 * MULTIPLIER),
                      "ETH_amount2": amount_a2,
                      "amount2": int(amount_a2 * MULTIPLIER),
                      "zeroForOne": zeroForOne,
                      "tick_shift1": ts1,
                      "tick_shift2": ts2,
                      "WETH_BUDGET": WETH_BUDGET,
                      }
            contexts = {"pool1": copy_context(context01),
                        "pool2": copy_context(context02)}
            result = simulated_attack3(inputs, targets, contexts)
            if not result is None:
                results.append(result)
            amount_a2 = round(amount_a2 + attack_step2, rounder2)
        amount_a1 = round(amount_a1 + attack_step1, rounder1)

df = pd.DataFrame(results)
# df.to_csv("path")
if zeroForOne:
    print(df.loc[df["resultToken0"].idxmax()])
else:
    print(df.loc[df["resultToken1"].idxmax()])
