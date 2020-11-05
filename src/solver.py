#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from itertools import chain, groupby
from math import fsum
from queue import PriorityQueue
from typing import Callable, Collection, Iterable, Union

from graph_model import App, Job, Task

from model import Core, Mapping, Problem, Processor, Solution

from timed import timed_callable


# SOLVING DICTS AND TYPE ALIASES ######################################################################################


"""Scheduling check, returns the sufficient condition."""
# Callable[[set[Task]], bool] = lambda tasks: workload(tasks) <= sufficient_condition(len(tasks))
SchedCheck = Callable[[Collection[Task], Collection[Core]], bool]
Ordering = Callable[[Iterable[Task]], Iterable[Task]]


"""Algorithms for scheduling, containing the sufficient condition, an ordering function."""
algorithms: dict[str, tuple[SchedCheck, Ordering]] = {
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

"""Maps a core to a set of tasks."""
CoreTaskMap = dict[Core, set[Task]]

"""Maps a processor to a tuple of set of applications and core map."""
ProcAppMap = dict[Processor, tuple[set[App], CoreTaskMap]]


# FUNCTIONS ###########################################################################################################


# optimization --------------------------------------------------------------------------------------------------------

def _optimization(problem: Problem, feasible_solution: dict) -> Solution:
	return Solution(problem.config, problem.graph.hyperperiod, 0, {})


# feasible scheduling -------------------------------------------------------------------------------------------------


def _feasible_scheduling(initial_solution: Mapping) -> Mapping:
	# check if child
	return initial_solution


# initial scheduling --------------------------------------------------------------------------------------------------


def _intersect(slice1: slice, slice2: slice) -> bool:
	return slice1.start <= slice2.start <= slice1.stop or slice1.start <= slice2.stop <= slice1.stop\
		or (slice2.start <= slice1.start and slice1.stop <= slice2.stop)


def _schedule_task(task: Task, core: Core, jobs: set[Job], hyperperiod: int) -> bool:
	# assign offset for each slot
	if len(task) == 0:
		for job in task:
			job.execution.add(slice(job.exec_window.start, job.exec_window.start + task.wcet))

		return True
	else:
		jobs_buffer: set[Job] = set()

		"""
		for c_job in jobs:
			offset = 0
			# check if conflicts and compute time available
			for t_job in task:
				if _intersect(t_job.exec_window, c_job.exec_window):
					pass
			# if total time available > task.wcet
				# make slices
			# else break

			jobs_buffer.add(Job(task, core, exec_window(slot.start + offset, slot.start + offset + task.wcet)))

			if int(hyperperiod / task.period) * task.wcet == task.execution_time():
				task.jobs |= jobs_buffer

				return True
			else:
				return False
		"""


def _initial_scheduling(initial_mapping: ProcAppMap, problem: Problem) -> CoreTaskMap:
	_, ordering = algorithms[problem.config.params.algorithm]
	flat_cores_tasks = {
		core: tasks for core_tasks in chain(
			core_tasks for _apps, core_tasks in initial_mapping.values()
		) for core, tasks in core_tasks.items()
	}

	# sort by crit, tasks
	# while True
		# modified = 0
		# for task in tasks
			# put if task has child and is after child
			# put it before
			# modified += 1
		# if modified != 0
			# break

	for core, tasks in flat_cores_tasks.items():
		print(core.pformat())
		for crit, _tasks in groupby(sorted(tasks, reverse=True), lambda t: t.criticality):
			print(f"\tcrit : {crit}")
			# for sorted by index when inorder
			for task in ordering(_tasks):
				print("\t\t" + task.app.name + "/" + str(task.id) + ((", " + str(task.child.id)) if task.child is not None else ""))
				# generate all slices at once depending on eventual previous task slices
				"""
				if not _schedule_task(task, core, task_slots[task], core_slices[core], problem.graph.hyperperiod):
					if crit < problem.graph.max_criticality:
						pass  # backtrack
					else:
						raise RuntimeError(f"Initial scheduling failed with task : '{task.app.name}/{task.id}'")
				"""

	return flat_cores_tasks


# initial mapping -----------------------------------------------------------------------------------------------------


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
	sched_check, _ = algorithms[problem.config.params.algorithm]

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
