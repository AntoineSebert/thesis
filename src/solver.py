#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from math import fsum
from typing import Callable, Iterable, TypeVar, Union

from graph_model import App, Criticality, Graph, Task

from model import Core, Mapping, Problem, Processor, Slice, Solution

from timed import timed_callable


# SOLVING DICTS AND TYPE ALIASES ######################################################################################


"""Scheduling check, returns the sufficient condition."""
# Callable[[set[Task]], bool] = lambda tasks: workload(tasks) <= sufficient_condition(len(tasks))
SchedCheck = Callable[[Iterable[Task]], bool]
Ordering = Callable[[Iterable[Task]], Iterable[Task]]


"""Policy for scheduling, containing the sufficient condition, an ordering function."""
policies: dict[str, tuple[SchedCheck, Ordering]] = {
	"edf": (
		lambda tasks: fsum(task.workload for task in tasks) <= (1 * 0.9), # replace 1 by n cores
		lambda tasks: sorted(tasks, key=lambda t: t.deadline),
	),
	"rm": (
		lambda tasks: fsum(task.workload for task in tasks) <= len(tasks) * (2**(1 / tasks) - 1), # replace by n cores
		lambda tasks: sorted(tasks, key=lambda t: t.period), #
	),
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
CoreTaskMap = dict[Core, tuple[set[Task], float]]

"""A mapping of cores to slices, representing the inital mapping."""
ProcAppMap = dict[Processor, tuple[set[App], CoreTaskMap]]

"""..."""
SlotMap = dict[Criticality, dict[Task, set[slice]]]
CoreSlotMap = dict[Core, SlotMap]

"""..."""
CoreSliceMap = dict[Core, set[Slice]]


# FUNCTIONS ###########################################################################################################


def _optimization(problem: Problem, feasible_solution: dict) -> Solution:
	return Solution(problem.config, problem.graph.hyperperiod, 0, {})


def _feasible_scheduling(initial_solution: Mapping) -> Mapping:
	# check if child
	return initial_solution


def _get_slots(task: Task, hyperperiod: int) -> set[slice]:
	return [slice(i * task.period, (i * task.period) + task.deadline) for i in range(int(hyperperiod / task.period))]


def _create_task_slots(core: Core, tasks: set[Task], hyperperiod: int) -> SlotMap:
	slot_map: SlotMap = {}

	for task in tasks:
		if task.criticality not in slot_map:
			slot_map[task.criticality] = {}
		slot_map[task.criticality][task] = _get_slots(task, hyperperiod)

	return dict(sorted(slot_map.items(), key=lambda x: x[0], reverse=True))


def _create_slot_map(initial_mapping: ProcAppMap, hyperperiod: int) -> CoreSlotMap:
	core_slot_map: CoreSlotMap = {}

	for _cpu, (_apps, core_tasks) in initial_mapping.items():
		for core, (tasks, _core_workload) in core_tasks.items():
			core_slot_map[core] = _create_task_slots(core, tasks, hyperperiod)

	return core_slot_map


def _intersect(slice1: Slice, slice2: Slice, switch_time: int = 0) -> bool:
	""" TODO
	1.
	A |-----------|
	B       |-----------|

	2.
	A       |-----------|
	B |-----------|

	3.
	A    |-------|
	B |-------------|

	4.
	A |-------------|
	B    |-------|
	"""
	return slice1.start - switch_time <= slice2.start <= slice1.stop + switch_time or slice1.start - switch_time <= slice2.stop <= slice1.stop + switch_time


def _initial_scheduling(initial_mapping: ProcAppMap, problem: Problem) -> CoreSliceMap:
	core_slot_map: CoreSlotMap = _create_slot_map(initial_mapping, problem.graph.hyperperiod)
	_, ordering = policies[problem.config.policy]
	core_slices: CoreSliceMap = {core: {} for core in core_slot_map.keys()}

	for core, crit_tasks in core_slot_map.items():
		for crit, task_slots in crit_tasks.items():
			for task in ordering(task_slots.keys()):
				# groupby()
					# for sorted by index
					# generate all slices at once depending on eventual previous task slices
				# assign offset for each slot
				if len(core_slices[core]) == 0:
					core_slices[core] = {
						Slice(task, core, slice(slot.start, slot.start + task.wcet)) for slot in task_slots[task]
					}
				else:
					slices: set[Slice] = set()

					for slot in task_slots[task]:
						offset = 0
						# check if conflicts and compute time available
						for _slice in core_slices[core]:
							# pass switch_time depending on same partition or not
							st = 0 if task.criticality == _slice.task.criticality else problem.config.switch_time
							if _intersect(_slice.et, slot, st):
								pass
						# if total time available > task.wcet
							# make slices
						# else break

						slices.add(Slice(task, core, slice(slot.start + offset + st, slot.start + offset + st + task.wcet)))

					execution_time = sum(_slice.et.stop - _slice.et.start for _slice in slices)
					if (total_execution_time := int(problem.graph.hyperperiod / task.period) * task.wcet) == execution_time:
						core_slices[core] |= slices
					elif execution_time < total_execution_time and crit < problem.graph.max_criticality:
						pass # backtrack
					else:
						pass #raise RuntimeError(f"Initial scheduling failed with task : '{task.app.name}/{task.id}'")

	for core, slices in core_slices.items():
		print(core.pformat())
		print('\t' + '\n\t'.join(f"{_slice.task.app.name}/{_slice.task.id}:{_slice.et}" for _slice in slices))

	return core_slices


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
			_tasks = tasks.copy()
			_tasks.add(task)
			# left-to-right conditional evaluation
			if len(tasks) == 0 or sched_check(_tasks):
				tasks.add(task)
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
	# use app-level and processor-level sched checks with len(cores) (or more like len(cpu) actually) + pqueue
	# bug with rate monotonic ?
	for cpu, (apps, core_tasks) in initial_mapping.items():
		buffer_mapping: CoreTaskMap = core_tasks.copy()

		if _map(buffer_mapping, app, sched_check):
			apps.add(app)
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
		cpu: (set(), {core: (set(), 0.0) for core in cpu}) for cpu in problem.arch
	}

	sched_check, _ = policies[problem.config.policy]

	for app in problem.graph.apps:
		if not _try_map(initial_mapping, app, sched_check):
			raise RuntimeError(f"Initial mapping failed with app : '{app.name}'")

	"""
	for core, crit_tasks in core_slot_map.items():
		print(core.pformat())
		for crit, task_slots in crit_tasks.items():
			print("\t" + str(crit))
			for task, slots in task_slots.items():
				print("\t\t" + task.app.name + "/" + str(task.id))
				print('\t\t\t' + '\n\t\t\t'.join(str(slot) for slot in slots))
	"""

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
	initial_solution = _initial_scheduling(initial_map, problem)
	feasible_solution = _feasible_scheduling(initial_solution)
	extensible_solution = _optimization(problem, feasible_solution)

	logging.info("Solution found for:\t" + str(problem.config.filepaths))

	return extensible_solution
