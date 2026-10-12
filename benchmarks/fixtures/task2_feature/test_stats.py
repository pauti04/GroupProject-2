from stats import median


def test_odd_length():
    assert median([3, 1, 2]) == 2


def test_even_length():
    assert median([4, 1, 3, 2]) == 2.5


def test_single_value():
    assert median([7]) == 7


def test_unsorted_input():
    assert median([9, 1, 5, 3, 7]) == 5
