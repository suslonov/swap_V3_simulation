#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from contract_caller import swap, mint, burn, collect, collect_all, copy_context
from contract_V3 import calc_liquidity_delta0, calc_liquidity_delta1
from contract_caller import swap_V2

MULTIPLIER = 10**18  # for attack amount lettice


# buying tokens from the same pool as providing liquidity
def simulated_attack1(inputs, targets, contexts, step=None):
    amountSpecified = inputs["amount"]
    zeroForOne = inputs["zeroForOne"]
    sqrtPriceLimitX96 = 0
    context = contexts["pool"]
    tick_spacing = context["tick_spacing"]
    ts1 = inputs["tick_shift1"]
    ts2 = inputs["tick_shift2"]
    if amountSpecified != 0:
        amounta0, amounta1, tick_diff = swap(zeroForOne, amountSpecified, sqrtPriceLimitX96, context)
    else:
        return None
    central_tick = context["slot0"]["tick"] // tick_spacing * tick_spacing

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
        return None
    # {"amountFrontrunningSwap": amountSpecified/1e18, "error": "zero minting"}
    amountm0, amountm1 = mint(central_tick + tick_spacing * ts1,
                                  central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                  mint_amount,
                                  context)
    if inputs["ETH_amount"] + (amountm0 if zeroForOne else amountm1) / MULTIPLIER > inputs["WETH_BUDGET"]:
        return None
    # {"amountFrontrunningSwap": amountSpecified/1e18, "error": "budget overflow"}
    for target in targets:
        amountTargetSpecified = int(target["amount_target"])
        amountv0, amountv1, tick_diff = swap(target["zeroForOne"], amountTargetSpecified, sqrtPriceLimitX96, context)
        if -(amountv1 if target["zeroForOne"] else amountv0) < target["amount_min"]:
            return None
        # {"amountFrontrunningSwap": amountSpecified/1e18, "error": "min target output"}

    amountb0, amountb1 = burn(central_tick + tick_spacing * ts1,
                              central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                              mint_amount,
                              context)

    amountc0, amountc1 = collect_all(central_tick + tick_spacing * ts1,
                                     central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                     context)

    amountcc0 = 0; amountcc1 = 0
#!!! check by price if this swap makes sense
    if zeroForOne:
        if amountc1 - amountm1 - amounta1 > 0:
            amountcc0, amountcc1, tick_diff = swap(0, amountc1 - amountm1 - amounta1, sqrtPriceLimitX96, context)
    else:
        if amountc0 - amountm0 - amounta0 > 0:
            amountcc0, amountcc1, tick_diff = swap(1, amountc0 - amountm0 - amounta0, sqrtPriceLimitX96, context)

    return {"tickLower": central_tick + tick_spacing * ts1,
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
                    "resultToken1Wei": (amountc1 - amountcc1 - amountm1 - amounta1)}

# buying tokens from 2 pools, V2 + V3, minting/burning on V3
def simulated_attack2(inputs, targets, contexts, step=None):
    amountSpecified1 = inputs["amount1"]
    amountSpecified2 = inputs["amount2"]
    zeroForOne = inputs["zeroForOne"]
    sqrtPriceLimitX96 = 0
    context1 = contexts["pool1"]
    context2 = contexts["pair"] #V2
    tick_spacing = context1["tick_spacing"]

    if step is None or step == 1:
        if amountSpecified1 != 0:
            amounta01, amounta11, tick_diff = swap(zeroForOne, amountSpecified1, sqrtPriceLimitX96, context1)
        else:
            amounta01 = 0; amounta11 = 0; tick_diff = 0;
        if amountSpecified2 != 0:
            amounta2 = swap_V2(zeroForOne, amountSpecified2, context2)
        else:
            amounta2 = 0
        context1["amounta01"] = amounta01
        context1["amounta11"] = amounta11
        context2["amounta2"] = amounta2
        if not step is None:
            return
        
    if step == 2:
        amounta01 = context1["amounta01"]
        amounta11 = context1["amounta11"]
        amounta2 = context2["amounta2"]
    
    ts1 = inputs["tick_shift1"]
    ts2 = inputs["tick_shift2"]
    central_tick = context1["slot0"]["tick"] // tick_spacing * tick_spacing

    if zeroForOne:
        if -amounta11 + amounta2 == 0:
            return None
        mint_amount = calc_liquidity_delta1(central_tick + tick_spacing * ts1,
                                            central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                            -amounta11 + amounta2,
                                            context1)
    else:
        if -amounta01 + amounta2 == 0:
            return None
        mint_amount = calc_liquidity_delta0(central_tick + tick_spacing * ts1,
                                            central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                            -amounta01 + amounta2,
                                            context1)
    if mint_amount == 0:
        return None
                # "error": "zero minting"}
    amountm0, amountm1 = mint(central_tick + tick_spacing * ts1,
                                  central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                  mint_amount,
                                  context1)
    if inputs["ETH_amount1"] + inputs["ETH_amount2"] + (amountm0 if zeroForOne else amountm1) / MULTIPLIER > inputs["WETH_BUDGET"]:
        return None
                # "error": "budget overflow"}

    for target in targets:
        amountTargetSpecified = int(target["amount_target"])
        amountv0, amountv1, tick_diff = swap(target["zeroForOne"], amountTargetSpecified, sqrtPriceLimitX96, context1)
        # print(amountv0, amountv1, tick_diff)
        if -(amountv1 if target["zeroForOne"] else amountv0) < target["amount_min"]:
            # break
            return None
                # "error": "min target output"}

    amountb0, amountb1 = burn(central_tick + tick_spacing * ts1,
                              central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                              mint_amount,
                              context1)

    amountc0, amountc1 = collect_all(central_tick + tick_spacing * ts1,
                                     central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                     context1)

    amountcc0 = 0; amountcc1 = 0
#!!! check by price if this swap makes sense
    if zeroForOne:
        if amountc1 - amountm1 - amounta11 + amounta2 > 0:
            amountcc0, amountcc1, tick_diff = swap(0, amountc1 - amountm1 - amounta11 + amounta2, sqrtPriceLimitX96, context1)
    else:
        if amountc0 - amountm0 - amounta01 + amounta2 > 0:
            amountcc0, amountcc1, tick_diff = swap(1, amountc0 - amountm0 - amounta01 + amounta2, sqrtPriceLimitX96, context1)

    return {"tickLower": central_tick + tick_spacing * ts1,
                    "tickUpper": central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                    "amountFrontrunningSwap1": amountSpecified1/1e18,
                    "amountFrontrunningSwap2": amountSpecified2/1e18,
                    "resultToken0": (amountc0 - amountcc0 - amountm0 - amounta01 + ( -amountSpecified2 if zeroForOne else amounta2))/1e18,
                    "resultToken1": (amountc1 - amountcc1 - amountm1 - amounta11 + (amounta2 if zeroForOne else -amountSpecified2))/1e18,
                    "swapWethInFronrun1": amountSpecified1,
                    "swapWethInFronrun2": amountSpecified2,
                    "mint_amount": mint_amount,
                    "providedAmount0": amountm0,
                    "providedAmount1": amountm1,
                    "burnAmount0": amountb0,
                    "burnAmount1": amountb0,
                    "collectAmount0": amountc0,
                    "collectAmount1": amountc1,
                    "swapAmountReceivedAfterCollect0": amountcc0,
                    "swapAmountReceivedAfterCollect1": amountcc1,
                    "resultToken0Wei": (amountc0 - amountcc0 - amountm0 - amounta01 + ( -amountSpecified2 if zeroForOne else amounta2)),
                    "resultToken1Wei": (amountc1 - amountcc1 - amountm1 - amounta11 + (amounta2 if zeroForOne else -amountSpecified2))}



# buying tokens from 2 pools, V2 + V3, minting/burning on V3
def simulated_attack3(inputs, targets, contexts, step=None):
    amountSpecified1 = inputs["amount1"]
    amountSpecified2 = inputs["amount2"]
    zeroForOne = inputs["zeroForOne"]
    sqrtPriceLimitX96 = 0
    context1 = contexts["pool1"]
    context2 = contexts["pool2"] #V2
    tick_spacing = context1["tick_spacing"]
    ts1 = inputs["tick_shift1"]
    ts2 = inputs["tick_shift2"]
    if amountSpecified1 != 0:
        amounta01, amounta11, tick_diff = swap(zeroForOne, amountSpecified1, sqrtPriceLimitX96, context1)
    else:
        amounta01 = 0; amounta11 = 0; tick_diff = 0;
    if amountSpecified2 != 0:
        amounta02, amounta12, tick_diff = swap(zeroForOne, amountSpecified2, sqrtPriceLimitX96, context2)
    else:
        amounta02 = 0; amounta12 = 0; tick_diff = 0;
    central_tick = context1["slot0"]["tick"] // tick_spacing * tick_spacing

    if zeroForOne:
        if -amounta11 - amounta12 == 0:
            return None
        mint_amount = calc_liquidity_delta1(central_tick + tick_spacing * ts1,
                                            central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                            -amounta11 - amounta12,
                                            context1)
    else:
        if -amounta01 - amounta02 == 0:
            return None
        mint_amount = calc_liquidity_delta0(central_tick + tick_spacing * ts1,
                                            central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                            -amounta01 - amounta02,
                                            context1)
    if mint_amount == 0:
        return None
                # "error": "zero minting"}
    amountm0, amountm1 = mint(central_tick + tick_spacing * ts1,
                                  central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                  mint_amount,
                                  context1)
    if inputs["ETH_amount1"] + inputs["ETH_amount2"] + (amountm0 if zeroForOne else amountm1) / MULTIPLIER > inputs["WETH_BUDGET"]:
        return None
                # "error": "budget overflow"}

    for target in targets:
        amountTargetSpecified = int(target["amount_target"])
        amountv0, amountv1, tick_diff = swap(target["zeroForOne"], amountTargetSpecified, sqrtPriceLimitX96, context1)
        # print(amountv0, amountv1, tick_diff)
        if -(amountv1 if target["zeroForOne"] else amountv0) < target["amount_min"]:
            return None

    amountb0, amountb1 = burn(central_tick + tick_spacing * ts1,
                              central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                              mint_amount,
                              context1)

    amountc0, amountc1 = collect_all(central_tick + tick_spacing * ts1,
                                     central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                                     context1)

    amountcc0 = 0; amountcc1 = 0
    
#!!! check by price if this swap makes sense
    if zeroForOne:
        if amountc1 - amountm1 - amounta11 - amounta12 > 0:
            amountcc0, amountcc1, tick_diff = swap(0, amountc1 - amountm1 - amounta11 - amounta12, sqrtPriceLimitX96, context1)
    else:
        if amountc0 - amountm0 - amounta01 - amounta02 > 0:
            amountcc0, amountcc1, tick_diff = swap(1, amountc0 - amountm0 - amounta01 - amounta02, sqrtPriceLimitX96, context1)

    return {"tickLower": central_tick + tick_spacing * ts1,
                    "tickUpper": central_tick + tick_spacing * ts1 + tick_spacing * ts2,
                    "amountFrontrunningSwap1": amountSpecified1/1e18,
                    "amountFrontrunningSwap2": amountSpecified2/1e18,
                    "resultToken0": (amountc0 - amountcc0 - amountm0 - amounta01 - amounta02)/1e18,
                    "resultToken1": (amountc1 - amountcc1 - amountm1 - amounta11 - amounta12)/1e18,
                    "swapWethInFronrun1": amountSpecified1,
                    "swapWethInFronrun2": amountSpecified2,
                    "mint_amount": mint_amount,
                    "providedAmount0": amountm0,
                    "providedAmount1": amountm1,
                    "burnAmount0": amountb0,
                    "burnAmount1": amountb0,
                    "collectAmount0": amountc0,
                    "collectAmount1": amountc1,
                    "swapAmountReceivedAfterCollect0": amountcc0,
                    "swapAmountReceivedAfterCollect1": amountcc1,
                    "resultToken0Wei": (amountc0 - amountcc0 - amountm0 - amounta01 - amounta02),
                    "resultToken1Wei": (amountc1 - amountcc1 - amountm1 - amounta11 - amounta12)}

