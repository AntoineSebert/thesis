#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from copy import deepcopy

from graph_model import App, Graph, Job

from mapper import mapping

from model import Architecture, Ordering, Problem, Processor, SchedCheck, Solution, Task, algorithms, empty_space

from scheduler import global_schedulability_test, schedule

from timed import timed_callable


# FUNCTIONS ###########################################################################################################


def _cpu_tasks_map(arch: Architecture, graph: Graph) -> dict[Processor, set[Task]]:
	cpu_tasks: dict[Processor, set[Task]] = dict.fromkeys(arch, set())

	for app in graph.apps:
		for task in app:
			cpu_tasks[task.cpu].add(task)

	return cpu_tasks


def _find_app_by_name(graph: Graph, name: str) -> App:
	for app in graph.apps:
		if app.name == name:
			return app

	raise RuntimeError(f"Failed to find app with {name=}.")


def _find_task_by_id(app: App, id: int) -> Task:
	for task in app:
		if task.id == id:
			return task

	raise RuntimeError(f"Failed to find task with {id=}.")


def _find_job_by_sched_window(task: Task, sched_window: slice) -> Job:
	for job in task:
		if job.sched_window == sched_window:
			return job

	raise RuntimeError(f"Failed to find job with {sched_window=}.")


def is_feasible(neighbor: Solution) -> bool:
	for app in neighbor.problem.graph.apps:
		for task in app:
			if task.has_miss() or not task.check_execution_time(neighbor.problem.graph.hyperperiod):
				print(f"{task.id} : deadline or exec miss")
				return False

	for app in neighbor.problem.graph.apps:
		if app.order:
			if app.has_order_miss():
				print(f"{app.name} : order miss")
				return False

	return True


def get_neighbors(solution: Solution, ordering: Ordering, sched_check: SchedCheck) -> list[Solution]:
	# print("=" * 100)
	candidates = []
	initial_step = solution.problem.config.params.initial_step

	for app in solution.problem.graph.apps:
		for task in app:
			for job in task:
				# print(f"{job.offset()=}")
				if task.wcet <= job.exec_window.stop - (job.exec_window.start + initial_step):
					neighbor = deepcopy(solution)

					for _app in neighbor.problem.graph.apps:
						for _task in _app:
							for _job in _task:
								_job.execution.clear()

					_app = _find_app_by_name(neighbor.problem.graph, app.name)
					_task = _find_task_by_id(app, task.id)
					_job = _find_job_by_sched_window(_task, job.exec_window)
					_job.exec_window = slice(_job.exec_window.start + initial_step, _job.exec_window.stop)
					# print(f"{_job.offset()=}")

					candidate = schedule(neighbor.core_jobs, neighbor.problem, ordering)

					if is_feasible(candidate):
						candidates.append(candidate)

	return candidates


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

	sched_check, ordering = algorithms[problem.config.params.algorithm]

	if global_schedulability_test(problem):
		core_jobs = mapping(problem.arch, problem.graph.apps, sched_check)
		initial_solution = schedule(core_jobs, problem, ordering)
		current = initial_solution
		generations = 0
		# get arrays of jobs for all tasks

		while (candidates := get_neighbors(current, ordering, sched_check)):
			generations += 1
			best_candidate = max(candidates, key=lambda c: empty_space(c))

			# either < or <=, should be ideally <= to explore full search space
			if (current_score := empty_space(current)) <= (best_score := empty_space(best_candidate)):
				current = best_candidate
			else:
				break

		logging.info("Solution found for:\t" + str(problem.config.filepaths))

		return current
	else:
		return None
