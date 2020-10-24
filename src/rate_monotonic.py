#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from fractions import Fraction
from typing import Callable

from model import Task


# FUNCTIONS ###########################################################################################################


"""Determine the sufficient condition for schedulability of a count of tasks.

Parameters
----------
count : int
	A number of processes.

Returns
-------
Fraction
	The sufficient workload rate for a count of tasks to be schedulable.
"""
sufficient_condition: Callable[[int], Fraction] = lambda count: count * (Fraction(2)**Fraction(1, count) - 1)


"""Determines whether an iterable of nodes is schedulable or not.

Parameters
----------
tasks : list[Node]
	An iterable of nodes representing periodic tasks.

Returns
-------
bool
	Returns 'True' if the tasks are schedulable, and 'False' otherise.
"""
is_schedulable: Callable[[list[Task]], bool] = lambda tasks: workload(tasks) <= sufficient_condition(len(tasks))
