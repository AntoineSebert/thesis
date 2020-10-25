#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from queue import PriorityQueue
from weakref import ref

from model import App, CoreTaskMap, Criticality, Graph, Problem, ProcAppMap, SchedCheck, Solution, policies

from timed import timed_callable


# FUNCTIONS ###########################################################################################################


def _create_task_pqueue(sched_check: SchedCheck, graph: Graph) -> dict[Criticality, PriorityQueue]:
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
	"""
	for criticality, tasks in groupby(sorted(tasks, key=key, reverse=True), key):
		tasks = list(tasks)
		crit_pqueue[criticality] = PriorityQueue(maxsize=len(tasks))
		for task in tasks:
			crit_pqueue[criticality].put((policy(task), task))
	"""
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


def _map(core_tasks: CoreTaskMap, app: App, sched_check: SchedCheck) -> bool:
	"""Tries to map the tasks of an application to the cores of a processor.

	Parameters
	----------
	core_tasks : CoreTaskMap
		A mapping of cores to tasks.
	app : App
		An application to map.
	sched_check : SchedCheck
		A scheduling check.

	Returns
	-------
	bool
		Returns `True` if the application have been mapped, or `False` otherwise.
	"""

	mapped_tasks: int = 0

	for task in app.tasks:
		for core, (tasks, core_workload) in core_tasks.items():
			# left-to-right conditional evaluation
			if len(tasks) == 0 or (core_workload + task.workload) < sched_check(len(tasks) + 1):
				tasks.add(ref(task))
				core_tasks[core] = (tasks, core_workload + task.workload)

				mapped_tasks += 1
				break

	return len(app.tasks) == mapped_tasks


def _try_map(initial_mapping: ProcAppMap, app: App, sched_check: SchedCheck) -> bool:
	"""Tries to map an application to a processor.

	Parameters
	----------
	initial_mapping : ProcAppMap
		A mapping of processors to applications.
	app : App
		An application to map.
	sched_check : SchedCheck
		A scheduling check.

	Returns
	-------
	bool
		Returns `True` if the application have been mapped, or `False` otherwise.
	"""

	# transform strategy for mapping : spread instead stack
	for cpu, (apps, core_tasks) in initial_mapping.items():
		buffer_mapping: CoreTaskMap = core_tasks.copy()

		if _map(buffer_mapping, app, sched_check):
			apps.add(ref(app))
			initial_mapping[cpu] = (apps, buffer_mapping)

			return True

	return False


def _initial_mapping(problem: Problem) -> ProcAppMap:
	"""Creates and returns a solution from the relaxed problem.

	Parameters
	----------
	problem : Problem
		A `Problem`.

	Returns
	-------
	ProcAppMap
		A mapping of the initial basis for the problem solving.
	"""

	initial_mapping: ProcAppMap = {
		ref(cpu): (set(), {ref(core): (set(), 0.0) for core in cpu.cores}) for cpu in problem.arch
	}

	for app in problem.graph.apps:
		if not _try_map(initial_mapping, app, policies[problem.config.policy]):
			raise f"Initial mapping failed with app : '{app.name}'"

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
