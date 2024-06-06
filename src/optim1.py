#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
os.sys.path.append(os.path.dirname(os.path.abspath('.')))
from web3 import Web3
from _utils.etherscan import _get_abi, _get_contract
from _utils.utils import RED, BLUE, GREEN, RESET_COLOR

from contract_caller import swap, mint, burn, collect, collect_all, init_context, copy_context
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

def get_contract(w3, address):
    abi = _get_abi(address, ETHERSCAN_KEY, abi_type="pool")
    return _get_contract(w3, abi, Web3.to_checksum_address(address))

w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

WETH_BUDGET = 200
MULTIPLIER = 10**18  # for attack amount lettice

####################    parameters    ############# 

# # example 1
# POOL = "0xC50f5f0E2421c307B3892a103B45B54f05259668"
# tx_block = 19430728
# zeroForOne = 0   #!!! don't forget about it !
# amount_target = 9 * 10**18
# multiplier = 10**17  # for attack amount lettice
# max_attack = 101
# #the second number is the liquidity range width in tick_spacing units
# tick_shifts = [(-2, 1), (-1, 1), (0, 1), (1, 1)] 

# # example 2
POOL = "0xc45A81BC23A64eA556ab4CdF08A86B61cdcEEA8b"
tx_block = 19368671
zeroForOne = 1   #!!! don't forget about it !
amount_target = 3319011000000000000
max_attack = 15 # WETH
attack_step = 0.00001
rounder = len(str(attack_step))

#the second number is the liquidity range width in tick_spacing units
tick_shifts = [(0, 1), (-1, 2)]
# tick_shifts = [(-2, 1), (-1, 1), (0, 1), (1, 1), (-1, 2)]
# tick_shifts = [(-7, 1), (-6, 1), (-5, 1), (-4, 1), (-3, 1), (-2, 1), (-1, 1), (0, 1), (1, 1)] 

# # example 3
# POOL = "0x11950d141EcB863F01007AdD7D1A342041227b58"
# tx_block = 19365747
# zeroForOne = 0   #!!! don't forget about it !
# amount_target = 10.271460191996691057 * 10**18
# multiplier = 10**17  # for attack amount lettice
# max_attack = 101
# #the second number is the liquidity range width in tick_spacing units
# tick_shifts = [(-2, 1), (-1, 1), (0, 1), (1, 1)] 

####################  end  parameters    ############# 

block = w3.eth.get_block(tx_block - 1)
prev_block_hash = block["hash"].hex()

context = {"w3": w3}
context["pool_address"] = POOL
context["pool_contract"] = get_contract(w3, POOL)
context["block_hash"] = prev_block_hash

# preload_ticks = int(max([2] + [abs(t[0]) for t in tick_shifts]) * 1.5)
init_context(context, 20) # preload +/- 10 ticks
sqrtPriceLimitX96 = 0
tick_spacing = context["tick_spacing"]
central_tick = context["slot0"]["tick"] // tick_spacing * tick_spacing
context0 = copy_context(context)

print("slot0 tick", context["slot0"]["tick"])
viewResults=[]
results = []
for ts1, ts2 in tick_shifts:
    print("liquidity providing: shift", ts1, "width", ts2)
    amount_a = attack_step
    while amount_a <= max_attack:
        context = copy_context(context0)

        amountSpecified = int(amount_a * MULTIPLIER)
        amounta0, amounta1, tick_diff = swap(zeroForOne, amountSpecified, sqrtPriceLimitX96, context)
        central_tick = context["slot0"]["tick"] // tick_spacing * tick_spacing
        # print("attack amount", amount_a, "central_tick", central_tick)

        if zeroForOne:
            mint_amount = calc_liquidity_delta1(central_tick + tick_spacing * ts1,
                                                central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                                -amounta1,
                                                context)
        else:
            mint_amount = calc_liquidity_delta0(central_tick + tick_spacing * ts1,
                                                central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                                -amounta0,
                                                context)
        if mint_amount == 0:
            amount_a = round(amount_a + attack_step, rounder)
            continue
        amountm0, amountm1 = mint(central_tick + tick_spacing * ts1,
                                  central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                  mint_amount,
                                  context)
        if amount_a + (amountm0 if zeroForOne else amountm1) / MULTIPLIER > WETH_BUDGET:
            amount_a = round(amount_a + attack_step, rounder)
            continue
        amountTargetSpecified = int(amount_target)
        amountv0, amountv1, tick_diff = swap(zeroForOne, amountTargetSpecified, sqrtPriceLimitX96, context)

        amountb0, amountb1 = burn(central_tick + tick_spacing * ts1,
                                  central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                  mint_amount,
                                  context)

        amountc0, amountc1 = collect_all(central_tick + tick_spacing * ts1,
                                         central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                         context)

        amountcc0 = 0; amountcc1 = 0
        if zeroForOne:
            if amountc1 - amountm1 - amounta1 > 0:
                amountcc0, amountcc1, tick_diff = swap(0, amountc1 - amountm1 - amounta1, sqrtPriceLimitX96, context)
        else:
            if amountc0 - amountm0 - amounta0 > 0:
                amountcc0, amountcc1, tick_diff = swap(1, amountc0 - amountm0 - amounta0, sqrtPriceLimitX96, context)

        results.append({"tickLower": central_tick + tick_spacing * ts1,
                        "tickUpper": central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                        "amountFrontrunningSwap": amountSpecified/1e18,
                        "resultToken0": (amountc0 - amountcc0 - amountm0 - amounta0)/1e18,
                        "resultToken1": (amountc1 - amountcc1 - amountm1 - amounta1)/1e18,
                        "swapWethInFronrun": amountSpecified,
                        "mint_amount": mint_amount,
                        "providedAmount0": amountm0,
                        "providedAmount1": amountm1,
                        "burnAmount0": amountb0,
                        "burnAmount1": amountb0,
                        "collectAmount0": amountc0,
                        "collectAmount1": amountc1,
                        "swapAmountReceivedAfterCollect0": amountcc0,
                        "swapAmountReceivedAfterCollect1": amountcc1,
                        "resultToken0Wei": (amountc0 - amountcc0 - amountm0 - amounta0),
                        "resultToken1Wei": (amountc1 - amountcc1 - amountm1 - amounta1)})

        amount_a = round(amount_a + attack_step, rounder)

df = pd.DataFrame(results)
# df.to_csv("path")
if zeroForOne:
    print(df.loc[df["resultToken0"].idxmax()])
    # # best results per range:
    # df.loc[df.groupby(["tickLower", "tickUpper"])["resultToken0"].idxmax()]
else:
    print(df.loc[df["resultToken1"].idxmax()])
    # # best results per range:
    # df.loc[df.groupby(["tickLower", "tickUpper"])["resultToken1"].idxmax()]

# df.sort_values(["tickLower", "tickUpper","amountFrontrunningSwap"])["resultToken0"].plot()
# df.plot.scatter("amountFrontrunningSwap", "resultToken0")
# df["resultToken0"].plot()
# df["resultToken1"].plot()
