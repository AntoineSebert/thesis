#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from queue import PriorityQueue
from typing import Iterable, List, Optional, Tuple, Dict, Callable

from model import Architecture, App, Task, PrioritizedItem, Problem, Processor, Slice, Solution
from edf import *
from rate_monotonic import workload

from timed import timed_callable


"""Main policy for scheduling, either rate monotonic or earliest deadline first."""
# make policies functions w/ LRU cache
policies: Dict[str, Callable[[List[Task]], List[Task]]] = {
	"edf": lambda task: task.deadline - task.offset,
	"rm": lambda task: task.wcet / task.period
}


constraints: List[Callable[[Problem, Solution], Solution]] = [
	lambda p, s: s,
	lambda p, s: s,
	lambda p, s: s,
	lambda p, s: s
]


objectives: Dict[str, Callable[[Solution], float]] = []


# FUNCTIONS ###########################################################################################################


def _create_task_pqueue(config: Configuration, graph : Graph) -> Dict[Criticality, PriorityQueue]:
	"""Creates a leveled priority queue for all tasks in the problem, depending on the criticality level and the scheduling policy.

	Parameters
	----------
	problem : Problem
		A `Problem`.

	Returns
	-------
	crit_pqueue : PriorityQueue[Task]
		A dictionary of criticality as keys and `PriorityQueue` objects containing tuples of task priority and task as values.
	"""

	crit_pqueue: Dict[Criticality, PriorityQueue[Task]] = {}
	tasks = [task for app in graph for task in app.tasks]
	key = lambda task: task.criticality

	for criticality, tasks in groupby(sorted(tasks, key=key), key):
		tasks = list(tasks)
		crit_pqueue[criticality] = PriorityQueue(maxsize=len(tasks))
		for task in tasks:
			crit_pqueue[criticality].put((policies[config.policy](task), task))

	return crit_pqueue


def _generate_solution(problem: Problem) -> Solution:
	"""Creates and returns a solution from the relaxed problem.

	Parameters
	----------
	problem : Problem
		A `Problem`.

	Returns
	-------
	Solution
		A `Solution`.
	"""

	crit_pqueue: Dict[Criticality, PriorityQueue] = _create_task_pqueue(problem.config, problem.graph)

	# check if available cores > processes to schedule then no conflicts !
	# do the incremental thingy
	# foreach level
		# foreach task
		# get least used core within task cpu
		# if not schedulable
			# if no backtrack possible
				# break highest contraint
			# else backtrack
		# else schedule

	return Solution(problem.config, problem.arch, _hyperperiod_duration(problem.arch), 0, {})


def _hyperperiod_duration(arch: Architecture) -> int:
	"""Computes the hyperperiod length for a solution.

	Parameters
	----------
	arch : Architecture
		The `Architecture` from a `Solution`.

	Returns
	-------
	int
		The hyperperiod length for the solution.
	"""

	return 0



# ENTRY POINT #########################################################################################################


@timed_callable("Solving the problem...")
def solve(problem: Problem) -> Solution:
	"""Creates the solution for a problem.

	Parameters
	----------
	problem : Problem
		A `Problem`.

	Returns
	-------
	solution : Solution
		A solution for the problem.
	"""

	solution = _generate_solution(problem)
	logging.info("Solution found for:\t" + str(problem.config.filepaths))

	return solution
