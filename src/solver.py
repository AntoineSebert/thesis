#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from copy import deepcopy

from algorithm import algorithms

from arch_model import CoreJobMap

from graph_model import Graph

from mapper import mapping

from model import Problem, Solution

from objective import objectives

from scheduler import schedule

from sortedcontainers import SortedSet  # type: ignore

from timed import timed_callable


# FUNCTIONS ###########################################################################################################


def _is_feasible(graph: Graph, core_jobs: CoreJobMap) -> bool:
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

	for jobs in core_jobs.values():
		for job in jobs:
			if job.has_execution_miss():
				return False

	"""
	for app in filter(lambda a: a.order, graph):
		for task in app:
			jobs = [job for jobs in core_jobs.values() for job in jobs if job.task is task]
			for i, job in enumerate(jobs[1:]):
				if not job < jobs[i]:
					return False
	"""

	return True


def get_neighbors(solution: Solution) -> list[Solution]:
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

	# print("=" * 200)
	candidates = []
	initial_step = solution.problem.config.params.initial_step

	for core, jobs in solution.core_jobs.items():
		for ii, job in enumerate(jobs):
			if job.task.wcet + initial_step <= job.exec_window.stop - job.exec_window.start:
				neighbor = deepcopy(solution.core_jobs)

				# TODO : alter mapping & check (need to put core_tasks in solution again)

				neighbor[core][ii].exec_window = slice(job.exec_window.start + initial_step, job.exec_window.stop)
				core_jobs = schedule(neighbor, solution.algorithm)

				if _is_feasible(solution.problem.graph, core_jobs):
					candidates.append(Solution(solution.problem, core_jobs, solution.objective, solution.algorithm))

	return sorted(candidates)


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

	_algorithm = algorithms[problem.config.params.algorithm]

	if (result := _algorithm.global_scheduling_check(problem.arch, problem.graph)) is not None:
		RuntimeError(f"Total workload is {result[0]}, should not be higher than {result[1]}.")

	explored_domain: list[SortedSet[Solution]] = [SortedSet()]
	explored_domain[0].add(
		Solution(
			problem,
			schedule(mapping(problem.arch, problem.graph.apps, _algorithm), _algorithm),
			objectives[problem.config.params.objective],
			_algorithm,
		),
	)

	# TODO :  if all apps have same crit and obj is cumulated free space, we can stop right here i guess

	while (candidates := get_neighbors(explored_domain[-1][0])):
		# print("#" * 200)

		if explored_domain[-1][0].score <= candidates[0].score:
			explored_domain.append(candidates)
		else:
			# solution with least offset_sum and same score as best solution
			if 1 < len(explored_domain):
				for i, solution_set in enumerate(reversed(explored_domain[1:])):
					if solution_set[0].score < explored_domain[-1][0].score:
						return explored_domain[i - 1]

	logging.info("Solution found for:\t" + str(problem.config.filepaths))

	"""
	for jobs in explored_solutions[-1].core_jobs.values():
		for job in jobs:
			print(job.pformat())
	"""

	return explored_domain[0][0]
