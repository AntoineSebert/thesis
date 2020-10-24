#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from itertools import groupby
from math import fsum
from queue import PriorityQueue
from typing import Callable, Optional
from weakref import ReferenceType, ref

from model import App, Core, Criticality, Graph, Mapping, Policy, policies, Problem, Processor, Slice, Solution, Task

from timed import timed_callable


# FUNCTIONS ###########################################################################################################


def get_core(task: Task, mapping: Mapping) -> Optional[ReferenceType[Core]]:
	"""Returns the first core a task can be scheduled on.

	Parameters
	----------
	task : Task
		An unscheduled `Task`.
	mapping : Mapping
		The current mapping.

	Returns
	-------
	Optional[ReferenceType[Core]]
		An optional reference to a core if one has been found.
	"""

	for core, slices in mapping.items():
		if len(slices) == 0:
			return core
		elif slices[-1]().stop < task.deadline:
			if task.wcet < (task.deadline - slices[-1]().stop):
				return core

	return None


def _create_task_pqueue(policy: Policy, graph: Graph) -> dict[Criticality, PriorityQueue]:
	"""Creates a leveled priority queue for all tasks in the problem, depending on the criticality level and the
	scheduling policy.

	Parameters
	----------
	policy: Policy
		A scheduling policy to sort the tasks.
	graph: Graph
		A task graph.

	Returns
	-------
	PriorityQueue[Task]
		A dictionary of criticality as keys and `PriorityQueue` objects containing tuples of task priority and task as
		values.
	"""

	crit_pqueue: dict[Criticality, PriorityQueue] = {}
	tasks = [task for app in graph.apps for task in app]
	key = lambda task: task.criticality

	for criticality, tasks in groupby(sorted(tasks, key=key, reverse=True), key):
		tasks = list(tasks)
		crit_pqueue[criticality] = PriorityQueue(maxsize=len(tasks))
		for task in tasks:
			crit_pqueue[criticality].put((policy(task), task))

	return crit_pqueue


def _optimization(problem: Problem, feasible_solution) -> Solution:
	return Solution(problem.config, problem.graph.hyperperiod, 0, {})


def _initial_scheduling(initial_mapping):
	"""
	crit_pqueue: dict[Criticality, PriorityQueue] = _create_task_pqueue(policies[problem.config.policy[0]], problem.graph)
	done: dict[Criticality, list[Task]] = {}
	mapping: Mapping = {}

	for cpu in problem.arch:
		for core in cpu:
			mapping[core] = []

	# foreach level
	for crit, pqueue in crit_pqueue.items():
		# foreach task
		while not pqueue.empty():
			priority, task = pqueue.get()

			# get least used core within task cpu
			core = get_core(task, mapping)

			# if not schedulable
			if core is None:
				# if no backtrack possible
				if crit == Criticality.sta_4:
					print("fail")
				# else backtrack
				else:
					print("compute backtrack")
			# else schedule
			else:
				if core in mapping and len(mapping[core]):
					start = mapping[core][-1].stop
				else:
					start = 0

				mapping[core].append(Slice(ref(task), ref(core), start, start + task.wcet))

			if crit not in done:
				done[crit] = []

			done[crit].append(task)
	"""

	return initial_mapping


def _try_map(initial_mapping: Mapping, app: App, policy: Policy) -> bool:

	for cpu, apps in initial_mapping.items():
		if len(apps) == 0:
			initial_mapping[cpu].add(ref(app))
			return True
		else:
			workload: float = app.workload() + fsum(_app().workload() for _app in apps)
			sc = policy(len(app) + sum(len(_app()) for _app in apps)) * len(cpu())
			print(str(workload) + ":" + str(sc))
			if workload <= sc:
				initial_mapping[cpu].add(ref(app))
				return True

	print("nope")
	return False


def _initial_mapping(problem: Problem) -> Mapping:
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

	initial_mapping: dict[ReferenceType[Processor], set[ReferenceType[App]]] = {
		ref(cpu): set() for cpu in problem.arch
	}

	for app in problem.graph.apps:
		if not _try_map(initial_mapping, app, policies[problem.config.policy]):
			pass  # throw(unschedulable)

	return initial_mapping


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

	initial_map = _initial_mapping(problem)
	feasible_solution = _initial_scheduling(initial_map)
	extensible_solution = _optimization(problem, feasible_solution)

	logging.info("Solution found for:\t" + str(problem.config.filepaths))

	return extensible_solution
