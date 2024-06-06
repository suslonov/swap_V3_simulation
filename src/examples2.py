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

#################################  

POOL = "0xC50f5f0E2421c307B3892a103B45B54f05259668"
tx_block = 19430728

context = {"w3": w3}
context["pool_address"] = POOL
context["pool_contract"] = get_contract(w3, POOL)
block = w3.eth.get_block(tx_block - 1)
prev_block_hash = block["hash"].hex()
context["block_hash"] = prev_block_hash

#################################  example 0

# init_context(context)
# print(GREEN, "only target exact token0 in", RESET_COLOR)
# amountTarget = 9
# amountTargetSpecified = int(amountTarget * 1e18)
# print(BLUE, amountTargetSpecified, RESET_COLOR)
# zeroForOne = 0
# sqrtPriceLimitX96 = 0
# amountt0, amountt1, tick_diff = swap(zeroForOne, amountTargetSpecified, sqrtPriceLimitX96, context)
# print(amountt0, amountt1, tick_diff)

# amount_in = 0.000001
# amountSpecified = int(amount_in * 1e18)
# zeroForOne = 0
# sqrtPriceLimitX96 = 0
# amountq0, amountq1, tick_diff = swap(zeroForOne, amountSpecified, sqrtPriceLimitX96, context)
# print(amountq0, amountq1, tick_diff, -amountq0/amountq1)


#################################  example 1

init_context(context)
# frontrun 0x07a2958d699ea67face1dd4c53844508a9c5f7e8863c69d0e0800207ed7eef1a
print(GREEN, "attack exact token0 in", RESET_COLOR)
# amount_in = 5
amountSpecified = 5014639163155518061
print(BLUE, amountSpecified, RESET_COLOR)
zeroForOne = 0
sqrtPriceLimitX96 = 0
amounta0, amounta1, tick_diff = swap(zeroForOne, amountSpecified, sqrtPriceLimitX96, context)
print(amounta0, amounta1, tick_diff)

mint_amount = calc_liquidity_delta0(-89400, -89200, -amounta0, context)
# mint_amount = 551275952347280761898561
# calc_liquidity_delta0(-89400, -89200, 37481799858227901985818, context)
# calc_liquidity_delta1(-89400, -89200, 58424701042331070974, context)
amountm0, amountm1 = mint(-89400, -89200, mint_amount, context)
print(BLUE, "mint", mint_amount, amountm0, amountm1, RESET_COLOR)

# target 0x101ab1fe30c294a3b0dd1198f6de23b46d8e0852b3220724ff8e07895d1be6e2
print(GREEN, "victim exact token0 in", RESET_COLOR)
amountTarget = 9
amountTargetSpecified = int(amountTarget * 1e18)
print(BLUE, amountTargetSpecified, RESET_COLOR)
amountv0, amountv1, tick_diff = swap(zeroForOne, amountTargetSpecified, sqrtPriceLimitX96, context)
print(amountv0, amountv1, tick_diff)

# backrun 0x3719d9a99d317cf100c545cf8b3f1af85dd28f5a1d6a6a6aea02951985685eb4
# mint_amount = 551275952347280761898561
amountb0, amountb1 = burn(-89400, -89200, mint_amount, context)
print(BLUE, "burn", amountb0, amountb1, RESET_COLOR)

amountc0, amountc1 = collect_all(-89400, -89200, context)
print(BLUE, "collect", amountc0, amountc1, RESET_COLOR)

print("attacker result token1")
print( (amountc1 - amountm1 - amounta1)/1e18)
print("attacker result token0")
print( (amountc0 - amountm0 - amounta0)/1e18)


#################################  example 2

POOL = "0xc45A81BC23A64eA556ab4CdF08A86B61cdcEEA8b"
tx_block = 19368671
zeroForOne = 1   #!!! don't forget about it !
amountTarget = 3.319011

context = {"w3": w3}
context["pool_address"] = POOL
context["pool_contract"] = get_contract(w3, POOL)
block = w3.eth.get_block(tx_block - 1)
prev_block_hash = block["hash"].hex()
context["block_hash"] = prev_block_hash

init_context(context, 10)
print(GREEN, "attack exact token0 in", RESET_COLOR)
# amountSpecified = 11373452608370574113
amountSpecified = 14067800000000000000
tickLower, tickUpper = 223400, 223800
print(BLUE, amountSpecified, RESET_COLOR)
sqrtPriceLimitX96 = 0
amounta0, amounta1, tick_diff = swap(zeroForOne, amountSpecified, sqrtPriceLimitX96, context)
print(amounta0, amounta1, tick_diff)

if zeroForOne:
    mint_amount = calc_liquidity_delta1(tickLower, tickUpper, -amounta1, context)
else:
    mint_amount = calc_liquidity_delta0(tickLower, tickUpper, -amounta0, context)
# mint_amount = 551275952347280761898561
# calc_liquidity_delta0(-89400, -89200, 37481799858227901985818, context)
# calc_liquidity_delta1(-89400, -89200, 58424701042331070974, context)
amountm0, amountm1 = mint(tickLower, tickUpper, mint_amount, context)
print(BLUE, "mint", mint_amount, amountm0, amountm1, RESET_COLOR)

# target 0x101ab1fe30c294a3b0dd1198f6de23b46d8e0852b3220724ff8e07895d1be6e2
print(GREEN, "victim exact token0 in", RESET_COLOR)
amountTargetSpecified = int(amountTarget * 1e18)
print(BLUE, amountTargetSpecified, RESET_COLOR)
amountv0, amountv1, tick_diff = swap(zeroForOne, amountTargetSpecified, sqrtPriceLimitX96, context)
print(amountv0, amountv1, tick_diff)

# backrun 0x3719d9a99d317cf100c545cf8b3f1af85dd28f5a1d6a6a6aea02951985685eb4
# mint_amount = 551275952347280761898561
amountb0, amountb1 = burn(tickLower, tickUpper, mint_amount, context)
print(BLUE, "burn", amountb0, amountb1, RESET_COLOR)

amountc00, amountc01 = collect_all(tickLower, tickUpper, context)
print(BLUE, "collect", amountc00, amountc01, RESET_COLOR)
amountc10, amountc11, tick_diff = swap((zeroForOne + 1) % 2, amountc01, sqrtPriceLimitX96, context)
print(BLUE, "convert", amountc10, amountc01, RESET_COLOR)

print("attacker result token0")
print( (amountc00 - amountc10 - amountm0 - amounta0)/1e18)
print("attacker result token1")
print( (amountc01 - amountc11 - amountm1 - amounta1)/1e18)



#################################  example 3

POOL = "0x11950d141EcB863F01007AdD7D1A342041227b58"
# tx_block = 19430728
tx_block = 19365747
zeroForOne = 0   #!!! don't forget about it !
amountTarget = 10.271460191996691057

context = {"w3": w3}
context["pool_address"] = POOL
context["pool_contract"] = get_contract(w3, POOL)
block = w3.eth.get_block(tx_block - 1)
prev_block_hash = block["hash"].hex()
context["block_hash"] = prev_block_hash


init_context(context)
print(GREEN, "attack exact token0 in", RESET_COLOR)
amountSpecified = 8993941428893054089
print(BLUE, amountSpecified, RESET_COLOR)
sqrtPriceLimitX96 = 0
amounta0, amounta1, tick_diff = swap(zeroForOne, amountSpecified, sqrtPriceLimitX96, context)
print(amounta0, amounta1, tick_diff)

if zeroForOne:
    mint_amount = calc_liquidity_delta1(-198720, -198660, -amounta1, context)
else:
    mint_amount = calc_liquidity_delta0(-198720, -198660, -amounta0, context)
# mint_amount = 551275952347280761898561
# calc_liquidity_delta0(-89400, -89200, 37481799858227901985818, context)
# calc_liquidity_delta1(-89400, -89200, 58424701042331070974, context)
amountm0, amountm1 = mint(-198720, -198660, mint_amount, context)
print(BLUE, "mint", amountm0, amountm1, RESET_COLOR)

# target 0x101ab1fe30c294a3b0dd1198f6de23b46d8e0852b3220724ff8e07895d1be6e2
print(GREEN, "victim exact token0 in", RESET_COLOR)
amountTargetSpecified = int(amountTarget * 1e18)
print(BLUE, amountTargetSpecified, RESET_COLOR)
amountv0, amountv1, tick_diff = swap(zeroForOne, amountTargetSpecified, sqrtPriceLimitX96, context)
print(amountv0, amountv1, tick_diff)

# backrun 0x3719d9a99d317cf100c545cf8b3f1af85dd28f5a1d6a6a6aea02951985685eb4
# mint_amount = 551275952347280761898561
amountb0, amountb1 = burn(-198720, -198660, mint_amount, context)
print(BLUE, "burn", amountb0, amountb1, RESET_COLOR)

amountc00, amountc01 = collect_all(-198720, -198660, context)
print(BLUE, "collect", amountc00, amountc01, RESET_COLOR)
amountc10, amountc11, tick_diff = swap((zeroForOne + 1) % 2, amountc01, sqrtPriceLimitX96, context)
print(BLUE, "convert", amountc10, amountc01, RESET_COLOR)

print("attacker result token0")
print( (amountc00 - amountc10 - amountm0 - amounta0)/1e18)
print("attacker result token1")
print( (amountc01 - amountc11 - amountm1 - amounta1)/1e18)

