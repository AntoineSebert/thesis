#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from queue import PriorityQueue

from graph_model import App

from model import Architecture, CoreJobMap, CoreTaskMap, Processor, SchedCheck

from sortedcontainers import SortedSet  # type: ignore


def _print_initial_mapping(core_jobs: CoreJobMap) -> None:
	"""Prints a mapping of cores to jobs.

	Parameters
	----------
	core_jobs : CoreJobMap
		A mapping of cores to jobs.
	"""

	for core, jobs in core_jobs.items():
		print(core.pformat())
		for job in jobs:
			print(job.pformat(1))


def _map_tasks_to_cores(core_tasks: CoreTaskMap, app: App, cpu: Processor) -> None:
	"""Maps all tasks of an application to the cores of a processor.

	Parameters
	----------
	core_tasks : CoreTaskMap
		A mapping of cores to tasks.
	app : App
		An application to map.
	cpu : Processor
		The processor onto which is scheduled the application.
	"""

	for task in app:
		core = cpu.get_min_core()

		core_tasks[core].add(task)
		core.workload += task.workload


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

	Raises
	------
	RuntimeError
		If an application cannot be scheduled on the least busy processor.
	"""

	core_tasks = {core: SortedSet() for cpu in arch for core in cpu}
	cpu_pqueue: PriorityQueue = PriorityQueue(maxsize=len(arch))

	for cpu in arch:
		cpu_pqueue.put(cpu)

	for app in apps:
		cpu = cpu_pqueue.get()

		if not cpu.apps or sched_check(app, cpu):
			_map_tasks_to_cores(core_tasks, app, cpu)
			cpu.apps.add(app)
		else:
			raise RuntimeError(f"Initial mapping failed with app '{app.name}' on CPU '{cpu.id}'.")

		cpu_pqueue.put(cpu)

	core_jobs = {core: [job for task in core_tasks[core] for job in task] for core in core_tasks.keys()}

	# _print_initial_mapping(core_jobs)

	return core_jobs
