#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from collections import defaultdict
from queue import PriorityQueue
from random import choice, sample

from algorithm import SchedAlgorithm

from arch_model import Architecture, Core, CoreJobMap

from graph_model import App, Graph, Task

from sortedcontainers import SortedSet  # type: ignore


Alteration = dict[App, dict[Core, set[Task]]]


def _print_initial_mapping(core_jobs: CoreJobMap) -> None:
	"""Prints a mapping of cores to jobs.

	Parameters
	----------
	core_jobs : CoreJobMap
		A mapping of cores to jobs.
	"""

	print("_print_initial_mapping")

	for core, jobs in core_jobs.items():
		print(core.short())
		for job in jobs:
			print(job.pformat(1))


def _print_alteration_possibilities(possibilities: Alteration) -> None:
	print("_print_alteration_possibilities")

	for app, core_tasks in possibilities.items():
		print(app.name)
		for core, tasks in core_tasks.items():
			print("\t" + core.short())
			for task in tasks:
				print("\t\t" + task.short())


def _get_core(arch: Architecture, task: Task) -> Core:
	for cpu in arch:
		for core in cpu:
			if task in core.tasks:
				return core

	raise RuntimeError(f"Could not find {task.short()} in the mapping.")


def _swap_tasks(possibilities: Alteration, app: App, cores: list[Core], task0: Task, task1: Task, neighbor: CoreJobMap) -> None:
	# actual swap
	cores[0].tasks.remove(task0)
	cores[1].tasks.append(task0)
	cores[0].tasks.append(task1)
	cores[1].tasks.remove(task1)

	for job in neighbor[cores[0]]:
		if job.task == task0:
			neighbor[cores[0]].append(job)
			neighbor[cores[0]].remove(job)

	for job in neighbor[cores[1]]:
		if job.task == task1:
			neighbor[cores[1]].append(job)
			neighbor[cores[1]].remove(job)

	# update alteration possibilities
	possibilities[app][cores[0]].remove(task0)
	possibilities[app][cores[1]].add(task0)
	possibilities[app][cores[1]].remove(task1)
	possibilities[app][cores[0]].add(task1)


# ENTRY POINT #########################################################################################################


def get_alteration_possibilities(arch: Architecture, graph: Graph) -> Alteration:
	possibilities: Alteration = {}

	for app in filter(lambda app: len(app) >= 2, graph):
		cores: dict[Core, set[Task]] = defaultdict(set)

		for task in app:
			cores[_get_core(arch, task)].add(task)

		if len(cores) >= 2:
			possibilities[app] = cores

	#_print_alteration_possibilities(possibilities)

	return possibilities


def alter_mapping(possibilities: Alteration, algorithm: SchedAlgorithm, neighbor: CoreJobMap) -> bool:
	# print("\nalter_mapping")

	app: App = choice(list(possibilities.keys()))
	cores: list[Core] = sample(list(possibilities[app].keys()), k=2)

	"""
	print('\t' + app.name)
	for core in cores:
		print('\t' + core.short())
	"""

	_swap_tasks(
		possibilities,
		app,
		cores,
		choice(list(possibilities[app][cores[0]])),
		choice(list(possibilities[app][cores[1]])),
		neighbor,
	)

	return algorithm.core_scheduling_check(cores[0]) and algorithm.core_scheduling_check(cores[1])


def mapping(arch: Architecture, apps: SortedSet[App], algorithm: SchedAlgorithm) -> CoreJobMap:
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

		if not cpu.apps or (result := algorithm.local_scheduling_check(cpu, app, algorithm.security_margin)) is None:
			cpu.apps.add(app)

			for task in app:
				cpu.min_core().tasks.append(task)
		else:
			raise RuntimeError(f"Initial mapping failed with app '{app.name}' on CPU '{cpu.id}': {result}.")

		cpu_pqueue.put(cpu)

	core_jobs = {}

	for cpu in arch:
		for core in cpu:
			if core.tasks:
				core_jobs[core] = [job for task in core for job in task]

	#_print_initial_mapping(core_jobs)

	return core_jobs
