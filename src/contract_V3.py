#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# https://docs.uniswap.org/contracts/v3/reference/core/interfaces/pool/IUniswapV3PoolState
# https://uniswapv3book.com/docs/milestone_3/
# https://github.com/Uniswap/v3-core/blob/main/contracts/UniswapV3Pool.sol
# https://uniswap.org/whitepaper-v3.pdf
# https://atiselsts.github.io/pdfs/uniswap-v3-liquidity-math.pdf

"""
How it works:
1) exact token0 in
        input:
            zeroForOne = 1; sqrtPriceLimitX96 = 0; amountSpecified > 0
        output:
            (token0, token1 < 0)
            
2) exact token1 in
        input:
            zeroForOne = 0; sqrtPriceLimitX96 = get_sqrt_ratio_at_tick(MAX_TICK); amountSpecified > 0
        output:
            (token0 < 0, token1)

3) exact token0 out
        input:
            zeroForOne = 0; sqrtPriceLimitX96 = get_sqrt_ratio_at_tick(MAX_TICK); amountSpecified < 0
        output:
            (token0 < 0, token1)

4) exact token1 out
        input:
            zeroForOne = 1; sqrtPriceLimitX96 = 0; amountSpecified < 0
        output:
            (token0, token1 < 0)

"""

from libs_V3 import MIN_TICK, MAX_TICK
from libs_V3 import get_tick_at_sqrt_ratio, get_sqrt_ratio_at_tick
from ticks_lib import next_initialized_tick_within_one_word, tick_flip
from ticks_lib import tick_cross, ticks_update, ticks_clear, ticks_getFeeGrowthInside
from swap_math import compute_swap_step, get_amount0_delta_, get_amount1_delta_
from swap_math import amount0_to_liquidity_delta, amount1_to_liquidity_delta
from swap_math import Q128

def _swap(zeroForOne, amountSpecified, sqrtPriceLimitX96, context):
    stored_slot0 = context["slot0"]
    liquidity = context["liquidity"]
    tick_spacing = context["tick_spacing"]
    fee = context["fee"]
    swap_cache = {
                "liquidityStart": liquidity,
                "feeProtocol": (stored_slot0["feeProtocol"] % 16) if zeroForOne else (stored_slot0["feeProtocol"] >> 4),
                "secondsPerLiquidityCumulativeX128": 0,
                "tickCumulative": 0,
                }
    
    exactInput = amountSpecified > 0

    swap_state = {
                "amountSpecifiedRemaining": amountSpecified,
                "amountCalculated": 0,
                "sqrtPriceX96": stored_slot0["sqrtPriceX96"],
                "tick": stored_slot0["tick"],
                "protocolFee": 0,
                "liquidity": swap_cache["liquidityStart"],
                "feeGrowthGlobalX128": context["feeGrowthGlobal0X128"] if zeroForOne else context["feeGrowthGlobal1X128"],

                }


    while swap_state["amountSpecifiedRemaining"] != 0 and swap_state["sqrtPriceX96"] != sqrtPriceLimitX96:
        step_computations = {
            "sqrtPriceStartX96": 0,
            "tickNext": 0,
            "initialized": False,
            "sqrtPriceNextX96": 0,
            "amountIn": 0,
            "amountOut": 0,
            "feeAmount": 0,
            }
            
        step_computations["sqrtPriceStartX96"] = swap_state["sqrtPriceX96"]

        step_computations["tickNext"], step_computations["initialized"] = next_initialized_tick_within_one_word(
                context["tick_bitmap_dict"],
                swap_state["tick"],
                tick_spacing,
                zeroForOne
                )
        
        if step_computations["tickNext"] < MIN_TICK:
            step_computations["tickNext"] = MIN_TICK
        elif step_computations["tickNext"] > MAX_TICK:
            step_computations["tickNext"] = MAX_TICK

        step_computations["sqrtPriceNextX96"] = get_sqrt_ratio_at_tick(step_computations["tickNext"])
        (swap_state["sqrtPriceX96"],
         step_computations["amountIn"],
         step_computations["amountOut"],
         step_computations["feeAmount"]) = compute_swap_step(
                swap_state["sqrtPriceX96"],
                sqrtPriceLimitX96 if (step_computations["sqrtPriceNextX96"] < sqrtPriceLimitX96
                                      if zeroForOne 
                                      else step_computations["sqrtPriceNextX96"] > sqrtPriceLimitX96) else step_computations["sqrtPriceNextX96"],
                swap_state["liquidity"],
                swap_state["amountSpecifiedRemaining"],
                fee)

        if exactInput:
            swap_state["amountSpecifiedRemaining"] -= step_computations["amountIn"] + step_computations["feeAmount"]
            swap_state["amountCalculated"] = swap_state["amountCalculated"] - step_computations["amountOut"]
        else:
            swap_state["amountSpecifiedRemaining"] += step_computations["amountOut"]
            swap_state["amountCalculated"] = swap_state["amountCalculated"] + step_computations["amountIn"] + step_computations["feeAmount"]

        if swap_cache["feeProtocol"] > 0:
            delta = step_computations["feeAmount"] // swap_cache["feeProtocol"]
            step_computations["feeAmount"] -= delta
            swap_state["protocolFee"] += delta

        if swap_state["liquidity"] > 0:
            swap_state["feeGrowthGlobalX128"] += step_computations["feeAmount"] * Q128 // swap_state["liquidity"]

        if swap_state["sqrtPriceX96"] == step_computations["sqrtPriceNextX96"]:
            if step_computations["initialized"]:
                liquidityNet = tick_cross(step_computations["tickNext"],
                        swap_state["feeGrowthGlobalX128"] if zeroForOne else context["feeGrowthGlobal0X128"],
                        context["feeGrowthGlobal1X128"] if zeroForOne else swap_state["feeGrowthGlobalX128"],
                        swap_cache["secondsPerLiquidityCumulativeX128"],
                        swap_cache["tickCumulative"],
                        context)

                if zeroForOne:
                    liquidityNet = -liquidityNet
                swap_state["liquidity"] = swap_state["liquidity"] + liquidityNet
            swap_state["tick"] = step_computations["tickNext"] - 1 if zeroForOne else step_computations["tickNext"]
        elif swap_state["sqrtPriceX96"] != step_computations["sqrtPriceStartX96"]:
            swap_state["tick"] = get_tick_at_sqrt_ratio(swap_state["sqrtPriceX96"])

    tick_diff = swap_state["tick"] - stored_slot0["tick"]
    if swap_state["tick"] != stored_slot0["tick"]:
        stored_slot0["sqrtPriceX96"], stored_slot0["tick"] = swap_state["sqrtPriceX96"], swap_state["tick"]
    else:
        stored_slot0["sqrtPriceX96"] = swap_state["sqrtPriceX96"]
    
    if swap_cache["liquidityStart"] != swap_state["liquidity"]:
        context["liquidity"] = swap_state["liquidity"]

    if zeroForOne:
        context["feeGrowthGlobal0X128"] = swap_state["feeGrowthGlobalX128"]
        # if (state.protocolFee > 0) protocolFees.token0 += state.protocolFee;
    else:
        context["feeGrowthGlobal1X128"] = swap_state["feeGrowthGlobalX128"]
        # if (state.protocolFee > 0) protocolFees.token1 += state.protocolFee;

    if zeroForOne == exactInput:
        amount0, amount1 = amountSpecified - swap_state["amountSpecifiedRemaining"], swap_state["amountCalculated"]
    else:
        amount0, amount1 = swap_state["amountCalculated"], amountSpecified - swap_state["amountSpecifiedRemaining"]

    return amount0, amount1, tick_diff


def position_update(liquidityDelta, feeGrowthInside0X128, feeGrowthInside1X128, context):

    if liquidityDelta == 0:
        liquidityNext = context["position.liquidity"];
    else:
        liquidityNext = context["position.liquidity"] + liquidityDelta

    tokensOwed0 = (feeGrowthInside0X128 - context["position.feeGrowthInside0LastX128"]) * context["position.liquidity"] // Q128
    tokensOwed1 = (feeGrowthInside1X128 - context["position.feeGrowthInside1LastX128"]) * context["position.liquidity"] // Q128
    
    if liquidityDelta != 0:
        context["position.liquidity"] = liquidityNext
        
    context["position.feeGrowthInside0LastX128"] = feeGrowthInside0X128
    context["position.feeGrowthInside1LastX128"] = feeGrowthInside1X128
    
    if tokensOwed0 > 0 or tokensOwed1 > 0:
        context["position.tokensOwed0"] += tokensOwed0
        context["position.tokensOwed1"] += tokensOwed1

def _updatePosition(tickLower, tickUpper, liquidityDelta, tick, context):

    if liquidityDelta != 0:
        flippedLower = ticks_update(
            tickLower,
            tick,
            liquidityDelta,
            context["feeGrowthGlobal0X128"],
            context["feeGrowthGlobal1X128"],
            # secondsPerLiquidityCumulativeX128,
            # tickCumulative,
            # time,
            False,
            context["max_liquidity_per_tick"],
            context)
        flippedUpper = ticks_update(
            tickUpper,
            tick,
            liquidityDelta,
            context["feeGrowthGlobal0X128"],
            context["feeGrowthGlobal1X128"],
            # secondsPerLiquidityCumulativeX128,
            # tickCumulative,
            # time,
            True,
            context["max_liquidity_per_tick"],
            context)

        if flippedLower:
            tick_flip(context["tick_bitmap_dict"], tickLower, context["tick_spacing"])
        if flippedUpper:
            tick_flip(context["tick_bitmap_dict"], tickUpper, context["tick_spacing"])


    feeGrowthInside0X128, feeGrowthInside1X128 = ticks_getFeeGrowthInside(tickLower,
                                                                          tickUpper,
                                                                          tick,
                                                                          context["feeGrowthGlobal0X128"],
                                                                          context["feeGrowthGlobal1X128"],
                                                                          context)
    position_update(liquidityDelta, feeGrowthInside0X128, feeGrowthInside1X128, context)

    if liquidityDelta < 0:
        if flippedLower:
            ticks_clear(tickLower, context)
        if flippedUpper:
            ticks_clear(tickUpper, context)


def _modifyPosition(tickLower, tickUpper, liquidityDelta, context):
    _slot0 = context["slot0"]
    _updatePosition(tickLower, tickUpper, liquidityDelta, _slot0["tick"], context)

    amount0 = 0
    amount1 = 0
    if liquidityDelta != 0:
        if _slot0["tick"] < tickLower:
            amount0 = get_amount0_delta_(get_sqrt_ratio_at_tick(tickLower),
                                         get_sqrt_ratio_at_tick(tickUpper),
                                         liquidityDelta)
        elif _slot0["tick"] < tickUpper:
            liquidityBefore = context["liquidity"]
            amount0 = get_amount0_delta_(_slot0["sqrtPriceX96"],
                                         get_sqrt_ratio_at_tick(tickUpper),
                                         liquidityDelta)
            amount1 = get_amount1_delta_(get_sqrt_ratio_at_tick(tickLower),
                                         _slot0["sqrtPriceX96"],
                                         liquidityDelta)

            context["liquidity"] = liquidityBefore + liquidityDelta
        else:
            amount1 = get_amount1_delta_(get_sqrt_ratio_at_tick(tickLower),
                                         get_sqrt_ratio_at_tick(tickUpper),
                                         liquidityDelta)
    return amount0, amount1


def calc_liquidity_delta0(tickLower, tickUpper, amount, context):
    _slot0 = context["slot0"]
    if _slot0["tick"] < tickLower:
        return amount0_to_liquidity_delta(get_sqrt_ratio_at_tick(tickLower),
                                          get_sqrt_ratio_at_tick(tickUpper),
                                          amount)
    elif _slot0["tick"] < tickUpper:
        return amount0_to_liquidity_delta(_slot0["sqrtPriceX96"],
                                          get_sqrt_ratio_at_tick(tickUpper),
                                          amount)
    else:
        return 0

def calc_liquidity_delta1(tickLower, tickUpper, amount, context):
    _slot0 = context["slot0"]
    # print(tickLower,_slot0["tick"], tickUpper)
    if _slot0["tick"] < tickLower:
        return 0
    elif _slot0["tick"] < tickUpper:
        return amount1_to_liquidity_delta(get_sqrt_ratio_at_tick(tickLower),
                                          _slot0["sqrtPriceX96"],
                                          amount)
    else:
        return amount1_to_liquidity_delta(get_sqrt_ratio_at_tick(tickLower),
                                          get_sqrt_ratio_at_tick(tickUpper),
                                          amount)


def _mint(tickLower, tickUpper, liquidity_delta, context):
    amount0, amount1 = _modifyPosition(tickLower, tickUpper, liquidity_delta, context)
    return amount0, amount1

def _burn(tickLower, tickUpper, liquidity_delta, context):
    amount0, amount1 = _modifyPosition(tickLower, tickUpper, -liquidity_delta, context)
    amount0 = -amount0
    amount1 = -amount1
    if amount0 > 0 or amount1 > 0:
        context["position.tokensOwed0"] += amount0
        context["position.tokensOwed1"] += amount1
    return amount0, amount1

def _collect(tickLower, tickUpper, amount0Requested, amount1Requested, context):
    amount0 = context["position.tokensOwed0"] if amount0Requested > context["position.tokensOwed0"] else amount0Requested
    amount1 = context["position.tokensOwed1"] if amount1Requested > context["position.tokensOwed1"] else amount1Requested

    if (amount0 > 0):
        context["position.tokensOwed0"] -= amount0;
    if (amount1 > 0):
        context["position.tokensOwed1"] -= amount1;
    return amount0, amount1
