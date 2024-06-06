#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
os.sys.path.append(os.path.dirname(os.path.abspath('.')))
from web3 import Web3
from _utils.etherscan import _get_abi, _get_contract
from _utils.utils import RED, BLUE, GREEN, RESET_COLOR

from contract_caller import swap, mint, burn, collect, collect_all, init_context, copy_context, zero_for_one_weth, swap_V2
from contract_V3 import calc_liquidity_delta0, calc_liquidity_delta1
from swap_math import MAX_UINT_160
import numpy as np
import pandas as pd

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

# 0xde6df6c8af7dd79299848ae9966407edd62cf121bac975a2fb349b03b514173c
# 

pair = "0xA43fe16908251ee70EF74718545e4FE6C5cCEc9f"
token = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"
tx_block = 19365747
zeroForOne = zero_for_one_weth(token)
max_attack = 15 # WETH
attack_step = 0.00001
rounder = len(str(attack_step))

pool = "0x11950d141EcB863F01007AdD7D1A342041227b58"
tx_block = 19365747
zeroForOne = 1   #!!! don't forget about it !
amount_target = 3319011000000000000
max_attack = 15 # WETH
attack_step = 0.00001
rounder = len(str(attack_step))

block = w3.eth.get_block(tx_block - 1)
prev_block_hash = block["hash"].hex()

context1 = {"w3": w3}
context1["version"] = "uniswap_V3"
context1["pool_address"] = pool
context1["pool_contract"] = get_contract(w3, pool)
context1["block_hash"] = prev_block_hash
init_context(context1)

context2 = {"w3": w3}
context2["version"] = "uniswap_V2"
context2["pair_address"] = pair
context2["pair_contract"] = get_contract(w3, pair, abi_type="pair")
context2["block_hash"] = prev_block_hash
init_context(context2)

amount_specified = 2698068248885906664
swap_V2(zeroForOne, amount_specified, context2)

targets = [(0, 247010486967449980), (0, 271460191996691057), (0, 7630582702422855440), (0, 70000000000000000), (0, 50000000000000000)]


import multiprocessing as mp
import os
import time

def info(title):
    print(title)
    print('module name:', 
          __name__, 
          'parent process:', 
          os.getppid(), 
          'process id:', 
          os.getpid(),
          os.cpu_count())

def f(context1, context2, q):
    info('function f')
    stop = False
    while True:
        while not q.empty():
            c = q.get()
            if c is None:
                stop = True
                print('stop')
                break
            else:
                info('function f')
                print('version=', c)
                if c == "uniswap_V3":
                    print(context1["pool_contract"].functions.slot0().call())
                elif c == "uniswap_V2":
                    print(context2["pair_contract"].functions.getReserves().call())
        if stop:
            break
        time.sleep(0.001)
                
def main():
    info('main line')
    # ctx = mp.get_context('spawn')
    ctx = mp.get_context('fork')
    # p1 = ctx.Process(target=f, args=(10, context1,))
    # p2 = ctx.Process(target=f, args=(10, context2,))
    q1 = ctx.Queue()
    q2 = ctx.Queue()
    p1 = ctx.Process(target=f, args=(context1, context2, q1,))
    p2 = ctx.Process(target=f, args=(context1, context2, q2,))
    p1.start()
    p2.start()

    for i in range(10):
        q1.put("uniswap_V3")
        q2.put("uniswap_V2")
        time.sleep(1)

    q1.put(None)
    q2.put(None)

    p1.join()
    p2.join()


