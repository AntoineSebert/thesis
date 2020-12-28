#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from queue import PriorityQueue

from graph_model import App

from model import Architecture, CoreJobMap, CoreTaskMap, SchedCheck

from sortedcontainers import SortedSet  # type: ignore


def _print_initial_mapping(core_jobs: CoreJobMap) -> None:
	"""Prints an initial mapping.

	Parameters
	----------
	core_tasks : CoreJobMap
		A mapping of cores to tasks.
	"""

	for core, jobs in core_jobs.items():
		print(core.pformat())
		for job in jobs:
			print(job.pformat(1))


def _try_map(core_tasks: CoreTaskMap, app: App, sched_check: SchedCheck) -> bool:
	"""Tries to map all tasks of an application to the cores of a processor.

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
		core_tasks[core].add(task)
		core.workload += task.workload
		core_pqueue.put(core)

	return True


# ENTRY POINT #########################################################################################################


def mapping(arch: Architecture, apps: SortedSet[App], sched_check: SchedCheck) -> CoreJobMap:
	"""Creates and returns a solution from the relaxed problem.

	Parameters
	----------
	problem : Problem
		A `Problem`.

	Returns
	-------
	core_tasks : CoreTaskMap
		A mapping of cores to tasks.
	"""

	core_tasks = {core: SortedSet() for cpu in arch for core in cpu}
	cpu_pqueue: PriorityQueue = PriorityQueue(maxsize=len(arch))

	for cpu in arch:
		cpu_pqueue.put(cpu)

	for app in apps:
		cpu = cpu_pqueue.get()

		if (not cpu.apps or sched_check(app, cpu)) and _try_map(core_tasks, app, sched_check):
			cpu.apps.add(app)
		else:
			raise RuntimeError(f"Initial mapping failed with app : '{app.name}'")

		cpu_pqueue.put(cpu)

	core_jobs = {core: [job for task in core_tasks[core] for job in task] for core in core_tasks.keys()}

	# _print_initial_mapping(core_jobs)

	return core_jobs
