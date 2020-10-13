#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from functools import singledispatch
from itertools import groupby
from queue import PriorityQueue
from typing import Callable, Dict, List

from model import Architecture, Configuration, Criticality, Graph, Problem, Processor, Solution, Task

from timed import timed_callable


"""Main policy for scheduling, either rate monotonic or earliest deadline first."""
# make policies functions w/ LRU cache
policies: Dict[str, Callable[[List[Task]], List[Task]]] = {
	"edf": lambda task: task.deadline - task.offset,
	"rm": lambda task: task.wcet / task.period,
}


constraints: List[Callable[[Problem, Solution], Solution]] = [
	lambda p, s: s,
	lambda p, s: s,
	lambda p, s: s,
	lambda p, s: s,
]


objectives: Dict[str, Callable[[Solution], float]] = []


# FUNCTIONS ###########################################################################################################


def _create_task_pqueue(config: Configuration, graph: Graph) -> Dict[Criticality, PriorityQueue]:
	"""Creates a leveled priority queue for all tasks in the problem, depending on the criticality level and the
	scheduling policy.

	Parameters
	----------
	problem : Problem
		A `Problem`.

	Returns
	-------
	crit_pqueue : PriorityQueue[Task]
		A dictionary of criticality as keys and `PriorityQueue` objects containing tuples of task priority and task as
		values.
	"""

	crit_pqueue: Dict[Criticality, PriorityQueue] = {}
	tasks = [task for app in graph for task in app.tasks]
	key = lambda task: task.criticality

	for criticality, tasks in groupby(sorted(tasks, key=key, reverse=True), key):
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

	for crit, pqueue in crit_pqueue.items():
		while not pqueue.empty():
			task = pqueue.get()
			print(task)

	"""
	foreach level
		foreach task
			get least used core within task cpu
			if not schedulable
				if no backtrack possible
					break highest contraint
				else backtrack
			else schedule
	"""

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


@singledispatch
def pretty_print(solution: Solution, level: int = 0) -> None:
	i = "\n" + ("\t" * level)

	print("\nsolution {"
		+ solution.config.pformat(level + 1)
		+ i + "\tarchitecture {" + ("").join([cpu.pformat(level + 2) for cpu in solution.arch]) + i + "\t}\n"
		+ f"\thyperperiod : {solution.hyperperiod};\n\t"
		+ f"score : {solution.score};\n\t"
		+ "mapping {" + "\n\t\t".join([f"{task} : {core};" for task, core in solution.mapping.items()]) + "}\n"
		+ "}\n")


@pretty_print.register
def _(problem: Problem, level: int = 0) -> None:
	i = "\n" + ("\t" * level)

	print("\nproblem {\t"
		+ problem.config.pformat(level + 1)
		+ i + "\tarchitecture {" + ("").join([cpu.pformat(level + 2) for cpu in problem.arch]) + i + "\t}"
		+ i + "\tgraph {" + ("").join([app.pformat(level + 2) for app in problem.graph]) + i + "\t}"
		+ "}\n")


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

	pretty_print(problem)
	pretty_print(solution)  # return solution
