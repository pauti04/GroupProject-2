"""Statistics helpers.

TODO: implement median(numbers) so the tests in test_stats.py pass.
The function must handle both odd- and even-length lists and must not
assume the input is already sorted.
"""


def mean(numbers):
    return sum(numbers) / len(numbers)
