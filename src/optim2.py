#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
os.sys.path.append(os.path.dirname(os.path.abspath('.')))
from web3 import Web3
from _utils.etherscan import _get_abi, _get_contract
from _utils.utils import RED, BLUE, GREEN, RESET_COLOR

from contract_caller import swap, mint, burn, init_context, copy_context
from contract_V3 import calc_liquidity_delta0, calc_liquidity_delta1
from swap_math import MAX_UINT_160

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

def get_abi(address, abi_type=None):
    return _get_abi(address, ETHERSCAN_KEY, abi_type=abi_type)

def get_contract(w3, abi, address):
    return _get_contract(w3, abi, Web3.to_checksum_address(address))

w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))
ticks_dict = {}
tick_bitmap_dict = {}
context = {"ticks_dict": ticks_dict,
           "tick_bitmap_dict": tick_bitmap_dict,
           "slot0": None,
           "w3": w3,
           "pool_address": None,
           "pool_contract": None,
           "block_hash": None,
           }


################################# 

POOL = "0xC50f5f0E2421c307B3892a103B45B54f05259668"
context["pool_address"] = POOL
pool_abi = get_abi(POOL, "pool")
context["pool_contract"] = get_contract(w3, pool_abi, POOL)
tx_block = 19430728
block = w3.eth.get_block(tx_block - 1)
prev_block_hash = block["hash"].hex()
context["block_hash"] = prev_block_hash


zeroForOne = 0
sqrtPriceLimitX96 = 0
init_context(context)
context0 = copy_context(context)

def sandwich(amount_a, context0):
    context = copy_context(context0)

    amountSpecified = int(amount_a * 1e18)
    amounta0, amounta1, tick_diff = swap(zeroForOne, amountSpecified, sqrtPriceLimitX96, context)

    mint_amount = calc_liquidity_delta0(-89400, -89200, -amounta0, context)
    amountm0, amountm1 = mint(-89400, -89200, mint_amount, context)

    amount_in = 9
    amountSpecified = int(amount_in * 1e18)
    amountv0, amountv1, tick_diff = swap(zeroForOne, amountSpecified, sqrtPriceLimitX96, context)

    amountb0, amountb1 = burn(-89400, -89200, mint_amount, context)

    return ((amountb1 - amounta1 - amountm1)/1e18), ((amountb0 - amounta0 - amountm0)/1e18)

def optim_callable(x):
    r1, r0 = sandwich(x, context0)
    print(x, r1, r0)
    return -r1
    
def optim_callback(xk, r=None, convergence=None):
    print(xk, r, convergence)

import scipy

res = scipy.optimize.minimize(fun=optim_callable,
                              x0=0.1,
                              method=None, 
                              bounds=[(0, 100)], 
                              callback=optim_callback,
                              options=None)
