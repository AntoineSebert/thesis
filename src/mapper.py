#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from queue import PriorityQueue
from random import choice, choices

from algorithm import SchedCheck

from arch_model import Architecture, Core, CoreJobMap, CoreTaskMap

from graph_model import App, Graph, Task

from sortedcontainers import SortedSet  # type: ignore


def _print_initial_mapping(core_jobs: CoreJobMap) -> None:
	"""Prints a mapping of cores to jobs.

	Parameters
	----------
	core_jobs : CoreJobMap
		A mapping of cores to jobs.
	"""

	print("_print_initial_mapping")

	for core, jobs in core_jobs.items():
		print(core.pformat())
		for job in jobs:
			print(job.pformat(1))


def _get_core(core_tasks: CoreTaskMap, task: Task) -> Core:
	for core, tasks in core_tasks.items():
		if task in tasks:
			return core

	raise RuntimeError(f"Could not find {task.short()} in the mapping.")


def _swap_tasks(core_tasks: CoreTaskMap, cores: list[Core], task1: Task, task2: Task) -> None:
	core_tasks[cores[0]].remove(task1)
	core_tasks[cores[1]].add(task1)
	core_tasks[cores[0]].add(task2)
	core_tasks[cores[1]].remove(task2)


# ENTRY POINT #########################################################################################################


def get_alteration_possibilities(graph: Graph, core_tasks: CoreTaskMap) -> dict[App, dict[Core, set[Task]]]:
	possibilities: dict[App, dict[Core, set[Task]]] = {}

	for app in filter(lambda app: len(app) >= 2, graph):
		cores: dict[Core, set[Task]] = {}

		for task in app:
			core = _get_core(core_tasks, task)

			if core not in cores:
				cores[core] = set()

			cores[core].add(task)

		if len(cores) >= 2:
			possibilities[app] = cores

	return possibilities


def alter_mapping(core_tasks: CoreTaskMap, possibilities: dict[App, dict[Core, set[Task]]]) -> None:
	if 1 < len(core_tasks.values()) and possibilities:  # make that static
		app: App = choice(list(possibilities.keys()))
		cores: list[Core] = choices(list(possibilities[app].keys()), k=2)
		task1: Task = choice(list(possibilities[app][cores[0]]))
		task2: Task = choice(list(possibilities[app][cores[1]]))

		_swap_tasks(core_tasks, cores, task1, task2)


def mapping(arch: Architecture, apps: SortedSet[App], sched_check: SchedCheck) -> CoreJobMap:
	"""Creates and returns a solution from the relaxed problem.

	Parameters
	----------
	problem : Problem
		A `Problem`.

	Returns
	-------
	core_jobs : CoreJobMap
		A mapping of cores to jobs.

	Raises
	------
	RuntimeError
		If an application cannot be scheduled on the least busy processor.
	"""

	cpu_pqueue: PriorityQueue = PriorityQueue(maxsize=len(arch))

	for cpu in arch:
		cpu_pqueue.put(cpu)

	for app in apps:
		cpu = cpu_pqueue.get()

		if not cpu.apps or sched_check(app, cpu):
			cpu.apps.add(app)

			for task in app:
				cpu.min_core().tasks.add(task)
		else:
			raise RuntimeError(f"Initial mapping failed with app '{app.name}' on CPU '{cpu.id}'.")

		cpu_pqueue.put(cpu)

	core_jobs = {}

	for cpu in arch:
		for core in cpu:
			if core.tasks:
				core_jobs[core] = SortedSet(job for task in core for job in task)

	#_print_initial_mapping(core_jobs)

	return core_jobs
