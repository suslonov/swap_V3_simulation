#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from web3 import Web3
from eth_abi import abi
from hexbytes import HexBytes
from contract_V3 import _swap, _mint, _burn, _collect
from libs_V3 import MIN_TICK, MAX_TICK, MIN_SQRT_RATIO, MAX_SQRT_RATIO, MAX_UINT_128
from ticks_lib import tick_spacing_to_max_liquidity_per_tick, tick_info
from _utils.etherscan import _get_contract
from _utils.Multicall2 import Multicall2_abi
from _utils.utils import s64
from contract_V2 import get_amount_out_v2_fixed_fee, get_amount_in_v2_fixed_fee

Multicall2_address = "0x5BA1e12693Dc8F9c48aAD8770482f4739bEeD696"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"

def multicall_call(Multicall2_contract, calls, block_hash):
    if block_hash is None:
        return Multicall2_contract.functions.aggregate(calls).call()
    else:
        return Multicall2_contract.functions.aggregate(calls).call(block_identifier=block_hash)

def zero_for_one_weth(token):
    return 0 if token.lower() < WETH else 1

def init_context(context, tick_preload_range=2):
    if not "version" in context or context["version"] == "uniswap_V3":
        init_context_V3(context, tick_preload_range)
    elif context["version"] == "uniswap_V2":
        init_context_V2(context)
    
def init_context_V2(context, tick_preload_range=2):
    contract = context["pair_contract"]
    r = contract.functions.getReserves().call(block_identifier=context["block_hash"])
    context["reserve0"] = r[0]
    context["reserve1"] = r[1]
    
def init_context_V3(context, tick_preload_range=2):
    contract = context["pool_contract"]
    
    Multicall2_contract = _get_contract(context["w3"],
                                        Multicall2_abi,
                                        Multicall2_address)
    _address = Web3.to_checksum_address(context["pool_address"],)

    calls = [
             (_address, HexBytes(contract.functions.tickSpacing()._encode_transaction_data())),
             (_address, HexBytes(contract.functions.fee()._encode_transaction_data())),
             (_address, HexBytes(contract.functions.liquidity()._encode_transaction_data())),
             (_address, HexBytes(contract.functions.feeGrowthGlobal0X128()._encode_transaction_data())),
             (_address, HexBytes(contract.functions.feeGrowthGlobal1X128()._encode_transaction_data())),
             (_address, HexBytes(contract.functions.slot0()._encode_transaction_data())),
             ]

    Multicall2_results = multicall_call(Multicall2_contract, calls, context["block_hash"])

    tick_spacing = abi.decode(["uint256"], Multicall2_results[1][0])[0]
    slot0 = abi.decode(["uint256", "uint256", "uint256", "uint256", "uint256", "uint256", "bool"],
                       Multicall2_results[1][5])
    
    current_tick = s64(slot0[1])
    current_tick_round = (current_tick // tick_spacing) * tick_spacing

    context["tick_spacing"] = tick_spacing
    context["max_liquidity_per_tick"] = tick_spacing_to_max_liquidity_per_tick(context["tick_spacing"])
    context["fee"] = abi.decode(["uint256"], Multicall2_results[1][1])[0]
    context["liquidity"] = abi.decode(["uint256"], Multicall2_results[1][2])[0]
    context["feeGrowthGlobal0X128"] = abi.decode(["uint256"], Multicall2_results[1][3])[0]
    context["feeGrowthGlobal1X128"] = abi.decode(["uint256"], Multicall2_results[1][4])[0]
    context["slot0"] = {"feeProtocol": slot0[5], "sqrtPriceX96": slot0[0], "tick": current_tick}
    context["position.liquidity"] = 0
    context["position.tokensOwed0"] = 0
    context["position.tokensOwed1"] = 0
    context["position.feeGrowthInside0LastX128"] = 0
    context["position.feeGrowthInside1LastX128"] = 0

    bitmap_range = (MIN_TICK//tick_spacing) >> 8
    ticks_preload = [i for i in range(-tick_preload_range, tick_preload_range + 1)]
    calls = [(_address,
                  HexBytes(contract.functions.ticks(current_tick_round + ts * tick_spacing)._encode_transaction_data()))
             for ts in ticks_preload]
    # get the current tick +/-2
    calls_before_tick_bitmap = len(calls)

    for i in range(bitmap_range, -bitmap_range):
        calls.append((_address, HexBytes(contract.functions.tickBitmap(i)._encode_transaction_data())))

    Multicall2_results = multicall_call(Multicall2_contract, calls, context["block_hash"])

    context["tick_bitmap_dict"] = {}
    for i, q in enumerate(Multicall2_results[1][calls_before_tick_bitmap:]):
        context["tick_bitmap_dict"][i + bitmap_range] =  abi.decode(["uint256"], q)[0]

    context["ticks_dict"] = {}
    for i, ts in enumerate(ticks_preload):
        one_tick = abi.decode(["uint128", "int128", "uint256", "uint256", "int56", "uint160", "uint32", "bool"],
                       Multicall2_results[1][i])
        context["ticks_dict"][current_tick_round + ts * tick_spacing] = tick_info(one_tick)


def copy_context(context):
    new_context = context.copy()
    new_context["ticks_dict"] = {tick: context["ticks_dict"][tick].copy() for tick in context["ticks_dict"]}
    new_context["tick_bitmap_dict"] = context["tick_bitmap_dict"].copy()
    new_context["slot0"] = context["slot0"].copy()
    new_context["context0"] = context
    return new_context

def brief_context(context):
    new_context = context.copy()
    if not "version" in context or context["version"] == "uniswap_V3":
        new_context["ticks_dict"] = {tick: context["ticks_dict"][tick].copy() for tick in context["ticks_dict"]}
        new_context["tick_bitmap_dict"] = context["tick_bitmap_dict"].copy()
        new_context["slot0"] = context["slot0"].copy()
        new_context["pool_contract"] = None
        new_context["context0"] = None
    else:
        new_context["pair_contract"] = None
    new_context["w3"] = None
    return new_context

def swap(zeroForOne, amountSpecified, sqrtPriceLimitX96, context):
    if sqrtPriceLimitX96 == 0:
        if zeroForOne == 0:
            sqrtPriceLimitX96 = MAX_SQRT_RATIO
        else:
            sqrtPriceLimitX96 = MIN_SQRT_RATIO 

    return _swap(zeroForOne, amountSpecified, sqrtPriceLimitX96, context)

def mint(tickLower, tickUpper, liquidity_delta, context):
    return _mint(tickLower, tickUpper, liquidity_delta, context)

def burn(tickLower, tickUpper, liquidity_delta, context):
    return _burn(tickLower, tickUpper, liquidity_delta, context)

def collect(tickLower, tickUpper, amount0Requested, amount1Requested, context):
    return _collect(tickLower, tickUpper, amount0Requested, amount1Requested, context)

def collect_all(tickLower, tickUpper, context):
    return _collect(tickLower, tickUpper, MAX_UINT_128, MAX_UINT_128, context)

def swap_V2(zeroForOne, amountSpecified, context):
    if zeroForOne:
        return get_amount_out_v2_fixed_fee(amountSpecified, context["reserve0"], context["reserve1"])
    else:
        return get_amount_out_v2_fixed_fee(amountSpecified, context["reserve1"], context["reserve0"])
