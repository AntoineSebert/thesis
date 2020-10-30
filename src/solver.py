#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from math import fsum
from queue import PriorityQueue
from typing import Callable, Collection, Iterable, Union

from graph_model import App, Criticality, Task

from model import Core, ExecSlice, Mapping, Problem, Processor, Solution, exec_window

from timed import timed_callable


# SOLVING DICTS AND TYPE ALIASES ######################################################################################


"""Scheduling check, returns the sufficient condition."""
# Callable[[set[Task]], bool] = lambda tasks: workload(tasks) <= sufficient_condition(len(tasks))
SchedCheck = Callable[[Collection[Task], Collection[Core]], bool]
Ordering = Callable[[Iterable[Task]], Iterable[Task]]


"""Policy for scheduling, containing the sufficient condition, an ordering function."""
policies: dict[str, tuple[SchedCheck, Ordering]] = {
	"edf": (
		lambda tasks, cores: fsum(task.workload for task in tasks) <= len(cores) * 0.9,
		lambda tasks: sorted(tasks, key=lambda t: t.deadline),
	),
	"rm": (
		lambda tasks, cores: fsum(task.workload for task in tasks)
			<= len(cores) * 0.9 * (len(tasks) * (2**(1 / len(tasks)) - 1)),
		lambda tasks: sorted(tasks, key=lambda t: t.period),
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
CoreTaskMap = dict[Core, set[Task]]

"""A mapping of processors to applications maps, representing the inital mapping."""
ProcAppMap = dict[Processor, tuple[set[App], CoreTaskMap]]

"""..."""
SlotMap = dict[Criticality, dict[Task, set[exec_window]]]
CoreSlotMap = dict[Core, SlotMap]

"""..."""
CoreSliceMap = dict[Core, set[ExecSlice]]


# FUNCTIONS ###########################################################################################################


# optimization --------------------------------------------------------------------------------------------------------

def _optimization(problem: Problem, feasible_solution: dict) -> Solution:
	return Solution(problem.config, problem.graph.hyperperiod, 0, {})


# feasible scheduling -------------------------------------------------------------------------------------------------


def _feasible_scheduling(initial_solution: Mapping) -> Mapping:
	# check if child
	return initial_solution


# initial scheduling --------------------------------------------------------------------------------------------------


def _get_slots(task: Task, hyperperiod: int) -> set[exec_window]:
	return [exec_window(i * task.period, (i * task.period) + task.deadline) for i in range(int(hyperperiod / task.period))]


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
		for core, tasks in core_tasks.items():
			core_slot_map[core] = _create_task_slots(core, tasks, hyperperiod)

	return core_slot_map


def _intersect(slice1: ExecSlice, slice2: ExecSlice) -> bool:
	return slice1.start <= slice2.start <= slice1.stop\
		or slice1.start <= slice2.stop <= slice1.stop\
		or (slice2.start <= slice1.start and slice1.stop <= slice2.stop)


def _check_execution_time(task: Task, slices: set[ExecSlice], hyperperiod: int) -> bool:
	return int(hyperperiod / task.period) * task.wcet == sum(_slice.et.stop - _slice.et.start for _slice in slices)


def _schedule_task(task: Task, core: Core, slots: set[exec_window], slices: set[ExecSlice], hyperperiod: int) -> bool:
	# assign offset for each slot
	if len(slices) == 0:
		slices = {ExecSlice(task, core, exec_window(slot.start, slot.start + task.wcet)) for slot in slots}

		return True
	else:
		slices_buffer: set[ExecSlice] = set()

		for slot in slots:
			offset = 0
			# check if conflicts and compute time available
			for _slice in slices:
				# pass switch_time depending on same partition or not
				if _intersect(_slice.et, slot):
					pass
			# if total time available > task.wcet
				# make slices
			# else break

			slices_buffer.add(ExecSlice(task, core, exec_window(slot.start + offset, slot.start + offset + task.wcet)))

			if _check_execution_time(task, slices_buffer, hyperperiod):
				slices |= slices_buffer

				return True
			else:
				return False


def _initial_scheduling(initial_mapping: ProcAppMap, problem: Problem) -> CoreSliceMap:
	core_slot_map: CoreSlotMap = _create_slot_map(initial_mapping, problem.graph.hyperperiod)
	_, ordering = policies[problem.config.policy]
	core_slices: CoreSliceMap = {core: set() for core in core_slot_map.keys()}

	for core, crit_tasks in core_slot_map.items():
		for crit, task_slots in crit_tasks.items():
			for task in ordering(task_slots.keys()):
				# groupby()
					# for sorted by index
					# generate all slices at once depending on eventual previous task slices
				if not _schedule_task(task, core, task_slots[task], core_slices[core], problem.graph.hyperperiod):
					if crit < problem.graph.max_criticality:
						pass  # backtrack
					else:
						raise RuntimeError(f"Initial scheduling failed with task : '{task.app.name}/{task.id}'")
	"""
	for core, slices in core_slices.items():
		print(core.pformat())
		print('\t' + '\n\t'.join(f"{_slice.task.app.name}/{_slice.task.id}:{_slice.et}" for _slice in slices))
	"""

	return core_slices


# initial mapping -----------------------------------------------------------------------------------------------------


def _get_tasks(core_tasks: CoreTaskMap, core: Core) -> set[Task]:
	"""Recovers a set of tasks associated with a core.

	Parameters
	----------
	core_tasks : CoreTaskMap
		A mapping of cores to sets of tasks.
	core : Core
		A core that is assumed to be present in the `CoreTaskMap`.

	Returns
	-------
	set[Task]
		The set of tasks associated with the core in the `CoreTaskMap`.
	"""

	tasks = set()
	changed = False

	for _core, _tasks in core_tasks.items():
		if _core.id == core.id:
			tasks = _tasks
			changed = True
			break

	if not changed:
		raise RuntimeError(f"Recovering of the tasks associated with the core '{core.processor.id}/{core.id}' failed")

	return tasks


def _try_map(core_tasks: CoreTaskMap, app: App, sched_check: SchedCheck) -> bool:
	"""Tries to map an application to a processor.

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

	core_pqueue: PriorityQueue = PriorityQueue(maxsize=len(core_tasks.keys()))

	for core in core_tasks.keys():
		core_pqueue.put(core)

	for task in app:
		core = core_pqueue.get()
		tasks = _get_tasks(core_tasks, core)  # dirty workaround as `tasks = core_tasks[core]` triggers a KeyError

		if not (len(tasks) == 0 or sched_check(tasks, [core])):
			return False

		tasks.add(task)
		core.workload += task.workload

		core_pqueue.put(core)

	return True


def _print_initial_mapping(initial_mapping: ProcAppMap) -> None:
	"""Prints an initial mapping.

	Parameters
	----------
	initial_mapping : ProcAppMap
		An initial mapping.
	"""

	for cpu, (apps, core_tasks) in initial_mapping.items():
		print(cpu.pformat() + '\n\t' + ', '.join(app.name for app in apps))
		for core, tasks in core_tasks.items():
			print(core.pformat(1))
			for task in tasks:
				print("\t\t" + task.app.name + "/" + str(task.id))


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

	initial_mapping: ProcAppMap = {}
	cpu_pqueue: PriorityQueue = PriorityQueue(maxsize=len(problem.arch))
	sched_check, _ = policies[problem.config.policy]

	for cpu in problem.arch:
		cpu_pqueue.put(cpu)
		initial_mapping[cpu] = (set(), {core: set() for core in cpu})

	for app in problem.graph.apps:
		cpu = cpu_pqueue.get()
		apps, core_tasks = initial_mapping[cpu]

		if (len(apps) == 0 or sched_check(app, cpu)) and _try_map(core_tasks, app, sched_check):
			apps.add(app)
		else:
			raise RuntimeError(f"Initial mapping failed with app : '{app.name}'")

		cpu_pqueue.put(cpu)

	_print_initial_mapping(initial_mapping)

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
