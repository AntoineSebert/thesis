#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from typing import Callable, TypeVar, Union
from weakref import ReferenceType, ref

from graph_model import App, Task

from model import Core, Mapping, Problem, Processor, Slice, Solution

from timed import timed_callable


# SOLVING DICTS AND TYPE ALIASES ######################################################################################


SCHED_CHECK = TypeVar('SCHED_CHECK', None, int)


"""Scheduling check, returns the sufficient condition."""
# Callable[[set[Task]], bool] = lambda tasks: workload(tasks) <= sufficient_condition(len(tasks))
SchedCheck = Callable[[SCHED_CHECK], float]  # TODO: update to work with worload from list of tasks instead


"""Policy for scheduling, containing the sufficient condition, an ordering function."""
policies: dict[str, SchedCheck] = {
	"edf": lambda _: 1,
	"rm": lambda count: count * (2**(1 / count) - 1),
}


"""Objective functions that assign a score to a feasible solution."""
ObjectiveFunction = Callable[['Solution'], Union[int, float]]


"""Objectives and descriptions."""
objectives = {
	"min_e2e": (
		"minimal end-to-end application delay",
		{
			"cmltd": (
				"cumulated; lower is better",
				lambda s: s,
			),
			"nrml": (
				"normal distribution; lower is better",
				lambda s: s,
			),
		},
	),
	"max_empty": (
		"maximal empty space",
		{
			"cmltd": (
				"cumulated; lower is better",
				lambda s: s,
			),
			"nrml": (
				"normal distribution; lower is better",
				lambda s: s,
			),
		},
	),
}

"""A mapping of cores as keys, to a tuple of tasks and a workload as values."""
CoreTaskMap = dict[ReferenceType[Core], tuple[set[ReferenceType[Task]], float]]

"""A mapping of cores to slices, representing the inital mapping."""
ProcAppMap = dict[ReferenceType[Processor], tuple[set[ReferenceType[App]], CoreTaskMap]]

"""..."""
CoreSlotMap = dict[ReferenceType[Core], dict[ReferenceType[Task], list[slice]]]

"""..."""
CoreSliceMap = dict[ReferenceType[Core], dict[ReferenceType[Task], list[Slice]]]


# FUNCTIONS ###########################################################################################################


def _optimization(problem: Problem, feasible_solution: dict) -> Solution:
	return Solution(problem.config, problem.graph.hyperperiod, 0, {})


def _feasible_scheduling(initial_solution: Mapping) -> Mapping:
	pass


def _get_slots(core: Core, task: Task, hyperperiod: int) -> list[slice]:
	return [slice(i * task.period, (i * task.period) + task.wcet) for i in range(int(hyperperiod / task.period))]


def _create_task_slots(initial_mapping: ProcAppMap, hyperperiod: int) -> CoreSlotMap:
	core_slot_map: CoreSlotMap = {}

	for _cpu, (_apps, core_tasks) in initial_mapping.items():
		for core, (tasks, _core_workload) in core_tasks.items():
			core_slot_map[core] = {task: _get_slots(core(), task(), hyperperiod) for task in tasks}

	return core_slot_map


def _initial_scheduling(initial_mapping: ProcAppMap, hyperperiod: int) -> Mapping:
	core_slot_map: CoreSlotMap = _create_task_slots(initial_mapping, hyperperiod)

	"""
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
	print(core_slot_map)

	return {}


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

	for task in app:
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
		ref(cpu): (set(), {ref(core): (set(), 0.0) for core in cpu}) for cpu in problem.arch
	}

	for app in problem.graph.apps:
		if not _try_map(initial_mapping, app, policies[problem.config.policy]):
			raise RuntimeError(f"Initial mapping failed with app : '{app.name}'")

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
	initial_solution = _initial_scheduling(initial_map, problem.graph.hyperperiod)
	feasible_solution = _feasible_scheduling(initial_solution)
	extensible_solution = _optimization(problem, feasible_solution)

	logging.info("Solution found for:\t" + str(problem.config.filepaths))

	return extensible_solution
