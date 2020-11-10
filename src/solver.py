#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from itertools import groupby
from math import fsum
from queue import PriorityQueue
from typing import Callable, Collection, Iterable, Union

from graph_model import App, Criticality, Job, Task

from model import Core, Mapping, Problem, Processor, Solution

from sortedcontainers import SortedSet  # type: ignore

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
CoreTaskMap = dict[Core, SortedSet[Task]]

"""Maps a processor to a tuple of set of applications and core map."""
ProcAppMap = dict[Processor, tuple[SortedSet[App], CoreTaskMap]]

"""Maps a core to a set of jobs."""
CoreJobMap = dict[Core, SortedSet[Job]]

"""Mapping of tasks to cores, sorted by criticality, then eventual ordering, and finally by scheduling algorithm."""
SortedMap = dict[Criticality, dict[Task, Core]]


# FUNCTIONS ###########################################################################################################


# optimization --------------------------------------------------------------------------------------------------------

def _optimization(problem: Problem, feasible_solution: dict) -> Solution:
	return Solution(problem.config, problem.graph.hyperperiod, 0, {})


# feasible scheduling -------------------------------------------------------------------------------------------------


def _feasible_scheduling(initial_solution: Mapping) -> Mapping:
	# check if parent
	return initial_solution


# initial scheduling --------------------------------------------------------------------------------------------------


def _overlap_before(slice1: slice, slice2: slice) -> bool:
	"""
	typical case:
	slice1 |--------|
	slice2        |--------|

	edge case 1:
	slice1 |---------|
	slice2  |--------|

	edge case 2:
	slice1 |------|
	slice2 |---------|
	"""
	return (slice1.start < slice2.start and slice2.start < slice1.stop <= slice2.stop)\
		or (slice1.start == slice2.start and slice1.stop < slice2.stop)


def _overlap_after(slice1: slice, slice2: slice) -> bool:
	"""
	typical case:
	slice1      |--------|
	slice2 |--------|

	edge case 1:
	slice1 |--------|
	slice2 |-------|

	edge case 2:
	slice1    |------|
	slice2 |---------|

	"""
	return (slice2.start <= slice1.start < slice2.stop and slice2.stop < slice1.stop)\
		or (slice2.start < slice1.start and slice1.stop == slice2.stop)


def _inside(slice1: slice, slice2: slice) -> bool:
	"""
	typical case:
	slice1    |------|
	slice2 |------------|

	edge case:
	slice1 |------------|
	slice2 |------------|
	"""
	return slice2.start <= slice1.start and slice1.stop <= slice2.stop


def _intersect(slice1: slice, slice2: slice) -> bool:
	return _overlap_before(slice1, slice2) or _overlap_after(slice1, slice2)\
		or _inside(slice1, slice2) or _inside(slice2, slice1)


def _get_runtime(slices: list[slice]) -> int:
	_sum = 0
	for _slice in slices:
		_sum += _slice.stop - _slice.start

	return _sum


def _get_intersect_slices(job: Job, c_jobs: SortedSet[Job]) -> list[slice]:
	slices = []

	for c_job in filter(lambda j: _intersect(job.exec_window, j.exec_window), c_jobs):
		for _slice in filter(lambda s: _intersect(job.exec_window, s), c_job):
			slices.append(_slice)  # check for partitions !

	_check_no_intersect(slices)  # check that the intersecting slices do not intersect between themselves

	return sorted(slices, key=lambda s: s.start)


def _check_no_intersect(slices: list[slice]) -> None:
	if len(slices) < 2:
		return

	for i in range(len(slices) - 1):
		for ii in range(i + 1, len(slices)):
			if _intersect(slices[i], slices[ii]):
				raise RuntimeError(f"Error : slices '{slices[i]}' and '{slices[ii]}' intersect.")


def _get_slices(job: Job, c_jobs: SortedSet[Job]) -> list[slice]:
	slices = _get_intersect_slices(job, c_jobs)

	job_slices = []
	remaining = job.task.wcet

	# eventual leading space
	if job.exec_window.start < slices[0].start:
		if remaining <= (space := slices[0].start - job.exec_window.start):
			return [slice(job.exec_window.start, job.exec_window.start + remaining)]
		else:
			job_slices.append(slice(job.exec_window.start, job.exec_window.start + space))
			remaining -= space

	for i in range(len(slices) - 1):
		if 0 < (space := slices[i + 1].start - slices[i].stop):
			if remaining <= space:
				job_slices.append(slice(slices[i].stop, slices[i].stop + remaining))
				return job_slices
			else:
				job_slices.append(slice(slices[i].stop, slices[i].stop + space))
				remaining -= space

	# eventual leading space
	if slices[-1].stop < job.exec_window.stop:
		if remaining <= (space := job.exec_window.stop - slices[-1].stop):
			job_slices.append(slice(slices[-1].stop, slices[-1].stop + space))
			return job_slices
		else:
			raise RuntimeError(f"Not enough running time to schedule {job.short()}.")

	return job_slices


def _generate_exec_slices(job: Job, slices: list[slice]) -> list[slice]:
	j_slices = []
	target_runtime = job.task.wcet

	# take slices until wcet has been all done (mind last slice might not be complete !)
	for _slice in slices:
		if target_runtime <= _slice.stop - _slice.start:
			j_slices.append(slice(_slice.start, _slice.start + target_runtime))
			break
		else:
			j_slices.append(_slice)

		target_runtime -= _slice.stop - _slice.start

	return j_slices


def _schedule_task(task: Task, core: Core, c_jobs: SortedSet[Job]) -> bool:
	if len(c_jobs) == 0:
		for job in task:
			job.execution.append(slice(job.exec_window.start, job.exec_window.start + task.wcet))
			c_jobs.add(job)
	else:
		for job in task:
			slices = _get_slices(job, c_jobs)
			# check if enough runtime
			if (runtime := _get_runtime(slices)) == task.wcet:
				job.execution.extend(slices)
			elif task.wcet < runtime:
				job.execution.extend(_generate_exec_slices(job, slices))
			else:
				return False

			c_jobs.add(job)

	return True


def _order_task_cores(initial_mapping: ProcAppMap, algorithm: str) -> SortedMap:
	_, ordering = algorithms[algorithm]

	task_core: dict[Task, Core] = {}
	for _apps, core_tasks in initial_mapping.values():
		for core, tasks in core_tasks.items():
			for task in tasks:
				task_core[task] = core

	crit_ordered_task_core: SortedMap = {
		app.criticality: {} for apps, core_tasks in initial_mapping.values() for app in apps
	}

	for apps, _core_tasks in initial_mapping.values():
		for crit, apps in groupby(reversed(apps), lambda a: a.criticality):
			for app in SortedSet(apps, key=lambda a: a.order):
				# schedulign algorithm
				for task in ordering(app) if app.order else app.tasks:
					crit_ordered_task_core[crit][task] = task_core[task]

	return crit_ordered_task_core


def _initial_scheduling(initial_mapping: ProcAppMap, max_crit: Criticality, algorithm: str, offset: int = 0) -> CoreTaskMap:
	crit_ordered_task_core = _order_task_cores(initial_mapping, algorithm)
	cotc_done: SortedMap = {app.criticality: {} for apps, core_tasks in initial_mapping.values() for app in apps}
	core_jobs: CoreJobMap = {
		core: SortedSet() for app, core_tasks in initial_mapping.values() for core in core_tasks.keys()
	}

	for crit, ordered_task_core in reversed(crit_ordered_task_core.items()):
		for task, core in ordered_task_core.items():
			if not _schedule_task(task, core, core_jobs[core]):
				if crit < max_crit:
					raise NotImplementedError  # backtrack
				else:
					raise RuntimeError(f"Initial scheduling failed with task : '{task.app.name}/{task.id}'.")

			cotc_done[crit][task] = core

	return initial_mapping


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


def _get_tasks(core_tasks: CoreTaskMap, core: Core) -> SortedSet[Task]:
	"""Recovers a set of tasks associated with a core.

	Parameters
	----------
	core_tasks : CoreTaskMap
		A mapping of cores to sets of tasks.
	core : Core
		A core that is assumed to be present in the `CoreTaskMap`.

	Returns
	-------
	SortedSet[Task]
		The set of tasks associated with the core in the `CoreTaskMap`.
	"""

	tasks = SortedSet()
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
		initial_mapping[cpu] = (SortedSet(), {core: SortedSet() for core in cpu})

	for app in problem.graph.apps:
		cpu = cpu_pqueue.get()
		apps, core_tasks = initial_mapping[cpu]

		if (len(apps) == 0 or sched_check(app, cpu)) and _try_map(core_tasks, app, sched_check):
			apps.add(app)
		else:
			raise RuntimeError(f"Initial mapping failed with app : '{app.name}'")

		cpu_pqueue.put(cpu)

	# _print_initial_mapping(initial_mapping)

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
	initial_solution = _initial_scheduling(initial_map, problem.graph.max_criticality(), problem.config.params.algorithm)
	feasible_solution = _feasible_scheduling(initial_solution)
	extensible_solution = _optimization(problem, feasible_solution)

	logging.info("Solution found for:\t" + str(problem.config.filepaths))

	return extensible_solution
