#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from libs_V3 import MIN_TICK, MAX_TICK, MAX_UINT_128
from libs_V3 import most_significant_bit, least_significant_bit

def next_initialized_tick_within_one_word(tick_bitmap, tick, tickSpacing, zeroForOne):
    compressed = tick // tickSpacing
    # if tick < 0 and tick % tickSpacing != 0:
    #     compressed -= 1

    if (zeroForOne):
        word_pos = compressed >> 8
        bit_pos = compressed % 256
        mask = (1 << bit_pos) - 1 + (1 << bit_pos)
        masked = tick_bitmap[word_pos] & mask

        initialized = masked != 0
        if initialized:
            next_tick = (compressed - int(bit_pos - most_significant_bit(masked))) * tickSpacing
        else:
            next_tick = (compressed - int(bit_pos)) * tickSpacing
    else:
        word_pos = (compressed + 1) >> 8
        bit_pos = (compressed + 1) % 256
        mask = ((1 << bit_pos) - 1) ^ 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
        masked = tick_bitmap[word_pos] & mask

        initialized = masked != 0
        if initialized:
            next_tick = (compressed + 1 + (least_significant_bit(masked) - bit_pos)) * tickSpacing
        else:
            next_tick = (compressed + 1 + (255 - bit_pos)) * tickSpacing
    return next_tick, initialized
    


def next_initialized_tick(tick_bitmap, tick, new_tick, tickSpacing, zeroForOne):
    compressed = tick // tickSpacing
    # if tick < 0 and tick % tickSpacing != 0:  #!!!  check it !
    #     compressed -= 1
    compressed_new_tick = new_tick // tickSpacing
    if new_tick < 0 and new_tick % tickSpacing != 0:
        compressed_new_tick -= 1

    word_pos = compressed >> 8
    word_pos_new_tick = compressed_new_tick >> 8
    bit_pos = compressed % 256
    if tick_bitmap[word_pos] & (1 << bit_pos):
        return tick
    
    if (zeroForOne):
        mask = (1 << bit_pos) - 1 + (1 << bit_pos)
        masked = tick_bitmap[word_pos] & mask
        if masked:
            new_bit_pos = most_significant_bit(masked)
            return (compressed + 1 - bit_pos + new_bit_pos) * tickSpacing
        word_pos -= 1
    else:
        mask = ((1 << bit_pos) - 1) ^ 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
        masked = tick_bitmap[word_pos] & mask
        if masked:
            new_bit_pos = least_significant_bit(masked)
            return (compressed + 1 - bit_pos + new_bit_pos) * tickSpacing
        word_pos += 1


    while tick_bitmap[word_pos]:
        bitmap_word = tick_bitmap[word_pos]
        if (zeroForOne):
            if bitmap_word != 0:
                return ((word_pos << 8) + most_significant_bit(bitmap_word)) * tickSpacing
            else:
                word_pos -= 1
                if word_pos < word_pos_new_tick:
                    break
        else:
            if bitmap_word != 0:
                return ((word_pos << 8) + least_significant_bit(tick_bitmap[word_pos])) * tickSpacing
            else:
                word_pos -= 1
                if word_pos < word_pos_new_tick:
                    break

    return None

def tick_spacing_to_max_liquidity_per_tick(tick_spacing):
    min_tick = MIN_TICK // tick_spacing * tick_spacing
    max_tick = MAX_TICK // tick_spacing * tick_spacing
    num_ticks = (max_tick - min_tick) // tick_spacing + 1
    return MAX_UINT_128 // num_ticks

def tick_flip(tick_bitmap, tick, tick_spacing):
    compressed = tick // tick_spacing
    word_pos = compressed >> 8
    bit_pos = compressed % 256

    mask = 1 << bit_pos;
    tick_bitmap[word_pos] ^= mask


# def tick_bitmap(context, pos):
#     if not pos in context["tick_bitmap_dict"]:
#         if context["block_hash"] is None:
#             context["tick_bitmap_dict"][pos] = context["pool_contract"].functions.tickBitmap(pos).call()
#         else:
#             context["tick_bitmap_dict"][pos] = context["pool_contract"].functions.tickBitmap(pos).call(block_identifier=context["block_hash"])
#     return context["tick_bitmap_dict"][pos]

def tick_info(tick_data):
    if tick_data is None:
        return {"liquidityGross": 0,
                "liquidityNet": 0,
                "feeGrowthOutside0X128": 0,
                "feeGrowthOutside1X128": 0,
                "tickCumulativeOutside": 0,
                "secondsPerLiquidityOutsideX128": 0,
                "secondsOutside": 0,
                "initialized": False,
                }
    else:
        return {"liquidityGross": tick_data[0],
                "liquidityNet": tick_data[1],
                "feeGrowthOutside0X128": tick_data[2],
                "feeGrowthOutside1X128": tick_data[3],
                "tickCumulativeOutside": tick_data[4],
                "secondsPerLiquidityOutsideX128": tick_data[5],
                "secondsOutside": tick_data[6],
                "initialized": tick_data[7],
                }

def ticks(context, tick):
    if not tick in context["ticks_dict"]:
        if context["block_hash"] is None:
            one_tick = context["pool_contract"].functions.ticks(tick).call()
        else:
            one_tick = context["pool_contract"].functions.ticks(tick).call(block_identifier=context["block_hash"])
        print("loading tick", tick)
        context["ticks_dict"][tick] = tick_info(one_tick)
        context["context0"]["ticks_dict"][tick] = tick_info(one_tick)
    else:
        if context["ticks_dict"][tick] is None:
            context["ticks_dict"][tick] = tick_info(None)
    return context["ticks_dict"][tick]

def tick_cross(tick,
               feeGrowthGlobal0X128,
               feeGrowthGlobal1X128,
                secondsPerLiquidityCumulativeX128,
                tickCumulative,
               # time,
               context):

    tick_info = ticks(context, tick)
    tick_info["feeGrowthOutside0X128"] = feeGrowthGlobal0X128 - tick_info["feeGrowthOutside0X128"]
    tick_info["feeGrowthOutside1X128"] = feeGrowthGlobal1X128 - tick_info["feeGrowthOutside1X128"]
    tick_info["secondsPerLiquidityOutsideX128"] = secondsPerLiquidityCumulativeX128 - tick_info["secondsPerLiquidityOutsideX128"]
    tick_info["tickCumulativeOutside"] = tickCumulative - tick_info["tickCumulativeOutside"]
    return tick_info["liquidityNet"]

def ticks_update(tick,
            tickCurrent,
            liquidityDelta,
            feeGrowthGlobal0X128,
            feeGrowthGlobal1X128,
            # secondsPerLiquidityCumulativeX128,
            # tickCumulative,
            # time,
            upper,
            max_liquidity_per_tick,
            context):

    tick_info = ticks(context, tick)
    liquidityGrossBefore = tick_info["liquidityGross"]
    liquidityGrossAfter = liquidityGrossBefore + liquidityDelta
    flipped = (liquidityGrossAfter == 0) != (liquidityGrossBefore == 0)
    if liquidityGrossBefore == 0:
        if tick <= tickCurrent:
            tick_info["feeGrowthOutside0X128"]= feeGrowthGlobal0X128
            tick_info["feeGrowthOutside1X128"] = feeGrowthGlobal1X128
        #     tick_info.secondsPerLiquidityOutsideX128 = secondsPerLiquidityCumulativeX128;
        #     tick_info.tickCumulativeOutside = tickCumulative;
        #     tick_info.secondsOutside = time;
        tick_info["initialized"] = True

    tick_info["liquidityGross"] = liquidityGrossAfter

    if upper:
        tick_info["liquidityNet"] = tick_info["liquidityNet"] - liquidityDelta
    else:
        tick_info["liquidityNet"] = tick_info["liquidityNet"] + liquidityDelta
    return flipped

def ticks_clear(tick, context):
    context["ticks_dict"][tick] = None

def ticks_getFeeGrowthInside(
    tickLower,
    tickUpper,
    tickCurrent,
    feeGrowthGlobal0X128,
    feeGrowthGlobal1X128, context):
    
    lower = context["ticks_dict"][tickLower]
    upper = context["ticks_dict"][tickUpper]

    if tickCurrent >= tickLower:
        feeGrowthBelow0X128 = lower["feeGrowthOutside0X128"]
        feeGrowthBelow1X128 = lower["feeGrowthOutside1X128"]
    else:
        feeGrowthBelow0X128 = feeGrowthGlobal0X128 - lower["feeGrowthOutside0X128"]
        feeGrowthBelow1X128 = feeGrowthGlobal1X128 - lower["feeGrowthOutside1X128"]

    if tickCurrent < tickUpper:
        feeGrowthAbove0X128 = upper["feeGrowthOutside0X128"]
        feeGrowthAbove1X128 = upper["feeGrowthOutside1X128"]
    else:
        feeGrowthAbove0X128 = feeGrowthGlobal0X128 - upper["feeGrowthOutside0X128"]
        feeGrowthAbove1X128 = feeGrowthGlobal1X128 - upper["feeGrowthOutside1X128"]

    feeGrowthInside0X128 = feeGrowthGlobal0X128 - feeGrowthBelow0X128 - feeGrowthAbove0X128
    feeGrowthInside1X128 = feeGrowthGlobal1X128 - feeGrowthBelow1X128 - feeGrowthAbove1X128
        
    return feeGrowthInside0X128, feeGrowthInside1X128
