# coding: utf-8
"""
    awwparse.actions
    ~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""


def store_last(previous, current):
    return current


def append_to_list(previous, current):
    if previous is None:
        previous = []
    previous.append(current)
    return previous


def add_to_set(previous, current):
    if previous is None:
        previous = set()
    previous.add(current)
    return previous


def add(previous, current):
    if previous is None:
        previous = 0
    return previous + current


def sub(previous, current):
    if previous is None:
        previous = 0
    return previous - current
