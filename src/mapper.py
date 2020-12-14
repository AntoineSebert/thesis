#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from queue import PriorityQueue

from graph_model import App, Task

from model import Architecture, Core, CoreTaskMap, Problem, ProcAppMap, SchedCheck, algorithms

from sortedcontainers import SortedSet  # type: ignore


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


# ENTRY POINT #########################################################################################################


def mapping(arch: Architecture, apps: SortedSet[App], sched_check: SchedCheck) -> ProcAppMap:
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
	cpu_pqueue: PriorityQueue = PriorityQueue(maxsize=len(arch))

	for cpu in arch:
		cpu_pqueue.put(cpu)
		initial_mapping[cpu] = (SortedSet(), {core: SortedSet() for core in cpu})

	for app in apps:
		cpu = cpu_pqueue.get()
		_apps, core_tasks = initial_mapping[cpu]

		if (len(_apps) == 0 or sched_check(app, cpu)) and _try_map(core_tasks, app, sched_check):
			_apps.add(app)
		else:
			raise RuntimeError(f"Initial mapping failed with app : '{app.name}'")

		cpu_pqueue.put(cpu)

	# _print_initial_mapping(initial_mapping)

	return initial_mapping
