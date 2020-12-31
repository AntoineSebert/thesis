#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from copy import deepcopy

from graph_model import Graph

from mapper import mapping

from model import Ordering, Problem, SchedCheck, Solution, algorithms, empty_space

from scheduler import global_schedulability_test, schedule

from timed import timed_callable


# FUNCTIONS ###########################################################################################################


def _is_feasible(graph: Graph) -> bool:
	"""Check if an app graph does not break any logical constraints.

	Parameters
	----------
	graph : Graph
		A `Graph`.

	Returns
	-------
	bool
		Returns `True` is all constraints holds, or `False` otherwise.
	"""

	return graph.check_deadlines() and graph.check_task_ordering() and graph.check_job_executions()


def _clear_job_executions(graph: Graph) -> None:
	"""Clears all the executions of the jobs to avoid execution slices accumulation.

	Parameters
	----------
	graph : Graph
		A `Graph`.
	"""

	for app in graph.apps:
		for task in app:
			for job in task:
				job.execution.clear()


def get_neighbors(solution: Solution, ordering: Ordering, sched_check: SchedCheck) -> list[Solution]:
	"""Gets the feasible scheduled neighbors (candidates) of a Solution.

	Parameters
	----------
	solution : Solution
		A target Solution.
	ordering : Ordering
		An ordering, like EDF or RM.
	sched_check : SchedCheck
		A schedulability checker.

	Returns
	-------
	candidates : list[Solution]
		A list of candidates, may be empty.
	"""

	# print("=" * 100)
	candidates = []
	initial_step = solution.problem.config.params.initial_step

	for app in solution.problem.graph.apps:
		for task in app:
			for job in task:
				# print(f"{job.offset()=}")
				if task.wcet <= job.exec_window.stop - (job.exec_window.start + initial_step):
					neighbor = deepcopy(solution)
					graph = neighbor.problem.graph

					_clear_job_executions(graph)

					_job = graph.find_app_by_name(app.name).find_task_by_id(task.id).find_job_by_sched_window(job.exec_window)
					_job.exec_window = slice(_job.exec_window.start + initial_step, _job.exec_window.stop)

					candidate = schedule(neighbor.core_jobs, neighbor.problem, ordering)

					if _is_feasible(candidate.problem.graph):
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
	Solution
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
