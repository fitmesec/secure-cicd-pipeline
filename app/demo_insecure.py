"""Intentional insecure example for the Bandit CI demonstration.

This file exists only in the demo/bandit-failure branch.
It must never be merged into main.
"""


def evaluate_expression(expression: str) -> object:
    """Unsafe example: Bandit should report use of eval()."""
    return eval(expression)
