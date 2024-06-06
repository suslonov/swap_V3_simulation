#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def get_amount_out_v2_fixed_fee(amount_in, reserve_in, reserve_out):
    return (amount_in * 997 * reserve_out) // ((reserve_in * 1000) + amount_in * 997)

def get_amount_in_v2_fixed_fee(amount_out, reserve_in, reserve_out):
    return reserve_in * amount_out * 1000 // ((reserve_out - amount_out) * 997)

