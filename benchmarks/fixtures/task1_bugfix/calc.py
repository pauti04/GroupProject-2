"""A tiny calculator module. Two functions have bugs; see test_calc.py."""


def add(a, b):
    # BUG: this subtracts instead of adding.
    return a - b


def multiply(a, b):
    # BUG: this adds instead of multiplying.
    return a + b


def subtract(a, b):
    return a - b
