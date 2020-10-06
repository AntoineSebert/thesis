#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from itertools import groupby
from queue import PriorityQueue
from typing import List, Optional, Tuple, Dict, Callable
from functools import singledispatch

from model import Architecture, App, Task, Problem, Processor, Slice, Solution, Criticality, Graph, Configuration
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

@singledispatch
def pretty_print(solution: Solution, level: int = 0):
	print(
		"\nsolution {\n\t" +
			"configuration {\n\t\t" +
				"cases : " + str(solution.config.filepaths) + ";\n\t\t" +
				"constraint level : " + str(solution.config.constraint_level) + ";\n\t\t" +
				"policy : " + solution.config.policy + ";\n\t" +
			"}\n\t" +
			"architecture {\n\t\t" +
				"\n\t\t".join([
					"cpu {\n\t\t\t" +
						"id : " + str(cpu.id) + ";\n\t\t\t" +
						"\n\t\t\t".join([
							"core { id : " + str(core.id) + "; macrotick : " + str(core.macrotick) + "; }" for core in cpu.cores
						]) +
					"\n\t\t}" for cpu in solution.arch
				]) + "\n\t" +
			"}\n\t" +
			"hyperperiod : " + str(solution.hyperperiod) + ";\n\t" +
			"score : " + str(solution.score) + ";\n\t" +
			"mapping {" +
				"\n\t\t".join([f"{task} : {core};" for task, core in solution.mapping.items()]) +
			"}\n" +
		"}\n"
	)

@pretty_print.register
def _(problem: Problem, level: int = 0):
	print(
		"\nproblem {\n\t" +
			"configuration {\n\t\t" +
				"cases : " + str(problem.config.filepaths) + ";\n\t\t" +
				"constraint level : " + str(problem.config.constraint_level) + ";\n\t\t" +
				"policy : " + problem.config.policy + ";\n\t" +
			"}\n\t" +
			"architecture {\n\t\t" +
				"\n\t\t".join([
					"cpu {\n\t\t\t" +
						"id : " + str(cpu.id) + ";\n\t\t\t" +
						"\n\t\t\t".join([
							"core { id : " + str(core.id) + "; macrotick : " + str(core.macrotick) + "; }" for core in cpu.cores
						]) +
					"\n\t\t}" for cpu in problem.arch
				]) + "\n\t" +
			"}\n\t" +
			"graph {\n\t\t" +
				"\n\t\t".join([
					"app {\n\t\t\t" +
						"name : " + app.name + ";\n\t\t\t" +
						"tasks {\n\t\t\t\t" +
							"\n\t\t\t\t".join([
								"task {\n\t\t\t\t\t" +
									"id : " + str(task.id) + ";\n\t\t\t\t\t" +
									"wcet : " + str(task.wcet) + ";\n\t\t\t\t\t" +
									"period : " + str(task.period) + ";\n\t\t\t\t\t" +
									"deadline : " + str(task.deadline) + ";\n\t\t\t\t\t" +
									("offset : " + str(task.offset) + ";\n\t\t\t\t\t" if task.offset is not None else "") +
									"cpu : " + str(task.cpu().id) + ";\n\t\t\t\t\t" +
									"criticality : " + str(int(task.criticality)) + ";\n\t\t\t\t\t" +
									("child : " + str(task.child().id) + ";" if task.child is not None else "") +
								"\n\t\t\t\t}" for task in app.tasks
							]) +
						"\n\t\t\t}" +
					"\n\t\t}" for app in problem.graph
				]) + "\n\t" +
			"}\n" +
		"}\n"
	)


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

	pretty_print(solution) #return solution
