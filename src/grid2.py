#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Implemented attack:
1)
    swap WETH_in -> token
    swap WETH_in2 -> token (V2)
    mint (token, WETH_additional)
2)
    target swap
3)
    burn (token_out, WETH_out)
    swap token_out -> WETH

"""

import os
os.sys.path.append(os.path.dirname(os.path.abspath('.')))
from datetime import datetime
from web3 import Web3
import numpy as np
import pandas as pd

from _utils.etherscan import _get_abi, _get_contract
from contract_caller import init_context, copy_context
from simulated_attack import simulated_attack2
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

token = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"
zeroForOne = zero_for_one_weth(token)

pool = "0x11950d141EcB863F01007AdD7D1A342041227b58"
max_attack1 = 2 # WETH
attack_step1 = 0.01
start_attack1 = attack_step1
rounder1 = len(str(attack_step1))

pair = "0xA43fe16908251ee70EF74718545e4FE6C5cCEc9f"
max_attack2 = 3 # WETH
attack_step2 = 0.001
start_attack2 = attack_step2
rounder2 = len(str(attack_step2))

tx_block = 19365747
block = w3.eth.get_block(tx_block - 1)
prev_block_hash = block["hash"].hex()

context1 = {"w3": w3}
context1["version"] = "uniswap_V3"
context1["pool_address"] = pool
context1["pool_contract"] = get_contract(w3, pool)
context1["block_hash"] = prev_block_hash
init_context(context1, 20) # preload +/- 10 ticks
context0 = copy_context(context1)

context2 = {"w3": w3}
context2["version"] = "uniswap_V2"
context2["pair_address"] = pair
context2["pair_contract"] = get_contract(w3, pair, abi_type="pair")
context2["block_hash"] = prev_block_hash
init_context(context2)

targets = [{"zeroForOne": 0, "amount_target": 247010486967449980, "amount_min": 0},
           {"zeroForOne": 0, "amount_target": 271460191996691057, "amount_min": 0},
           {"zeroForOne": 0, "amount_target": 7630582702422855440, "amount_min": 0},
           {"zeroForOne": 0, "amount_target": 70000000000000000, "amount_min": 0},
           {"zeroForOne": 0, "amount_target": 50000000000000000, "amount_min": 0}]


#the second number is the liquidity range width in tick_spacing units
tick_shifts = [(0, 1), (1, 1), (-1, 2)]

####################  end  parameters    ############# 

t0 = datetime.now()
print("slot0 tick", context1["slot0"]["tick"])
results = []
for ts1, ts2 in tick_shifts:
    # print("liquidity providing: shift", ts1, "width", ts2)
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
            contexts = {"pool1": copy_context(context0),
                        "pair": context2}
            result = simulated_attack2(inputs, targets, contexts)
            if not result is None:
                results.append(result)
            amount_a2 = round(amount_a2 + attack_step2, rounder2)
        amount_a1 = round(amount_a1 + attack_step1, rounder1)

print((datetime.now() - t0).total_seconds())

df = pd.DataFrame(results)
# df.to_csv("path")
if zeroForOne:
    print(df.loc[df["resultToken0"].idxmax()])
else:
    print(df.loc[df["resultToken1"].idxmax()])


# tickLower                                               -198540
# tickUpper                                               -198480
# amountFrontrunningSwap1                                    20.0
# amountFrontrunningSwap2                                    2.88
# resultToken0                                                0.0
# resultToken1                                           0.163523
# swapWethInFronrun1                         20000000000000000000
# swapWethInFronrun2                          2880000000000000000
# mint_amount                         159247648525296407176864772
# providedAmount0                    9762186424528181983919781177
# providedAmount1                                               0
# burnAmount0                        7447828986079786200265639552
# burnAmount1                        7447828986079786200265639552
# collectAmount0                     7447828986079786200265639552
# collectAmount1                              5546158003869994993
# swapAmountReceivedAfterCollect0    7447828986079786200265639566
# swapAmountReceivedAfterCollect1           -17497365063689261657
# resultToken0Wei                                               0
# resultToken1Wei                              163523067559256650
# Name: 3847017, dtype: object

# df.loc[(df["tickLower"] == -198720)
#         & (df["tickUpper"] == -198660)
#         & (df["amountFrontrunningSwap2"] == 2.69),
#         ["amountFrontrunningSwap1", "resultToken1"]].set_index(["amountFrontrunningSwap1"]).sort_index().plot()
# df.loc[(df["tickLower"] == -198720)
#         & (df["tickUpper"] == -198660)
#         & (df["amountFrontrunningSwap1"] == 8.99),
#         ["amountFrontrunningSwap2", "resultToken1"]].set_index(["amountFrontrunningSwap2"]).sort_index().plot()


# df.loc[(df["tickLower"] == -198720) &
#        (df["tickUpper"] == -198660) &
#        (df["amountFrontrunningSwap1"] == 8.99) &
#        (df["amountFrontrunningSwap2"] == 2.69)].T

#                                                       2745998
# tickLower                                             -198720
# tickUpper                                             -198660
# amountFrontrunningSwap1                                  8.99
# amountFrontrunningSwap2                                  2.69
# resultToken0                                              0.0
# resultToken1                                          0.08183
# swapWethInFronrun1                        8990000000000000000
# swapWethInFronrun2                        2690000000000000000
# mint_amount                        81254907431586128453175519
# providedAmount0                  5026111554737935604501023820
# providedAmount1                                             0
# burnAmount0                      2982882558625635935444438515
# burnAmount1                      2982882558625635935444438515
# collectAmount0                   2982882558625635935444438515
# collectAmount1                            4811523161282339697
# swapAmountReceivedAfterCollect0  2982882558625635935444438519
# swapAmountReceivedAfterCollect1          -6950306540666562691
# resultToken0Wei                                             0
# resultToken1Wei                             81829701948902388