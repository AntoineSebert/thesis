#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from copy import deepcopy

from algorithm import Ordering, SchedCheck, algorithms

from arch_model import CoreJobMap

from graph_model import Graph

from mapper import mapping

from model import Problem, Solution

from objective import objectives

from scheduler import global_schedulability_test, schedule

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

	for app in filter(lambda a: a.order, graph):
		for task in app:
			jobs = [job for jobs in core_jobs.values() for job in jobs if job.task is task]
			for i, job in enumerate(jobs[1:]):
				if not job < jobs[i]:
					return False

	return True


def _clear_job_executions(core_jobs: CoreJobMap) -> None:
	"""Clears all the executions of the jobs to avoid execution slices accumulation.

	Parameters
	----------
	graph : Graph
		A `Graph`.
	"""

	for jobs in core_jobs.values():
		for job in jobs:
			job.execution.clear()


def get_neighbors(solution: Solution, ordering: Ordering, sched_check: SchedCheck) -> SortedSet[Solution]:
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
	candidates : SortedSet[Solution]
		A list of candidates, may be empty.
	"""

	#print("=" * 200)
	candidates = SortedSet()
	initial_step = solution.problem.config.params.initial_step

	for core, jobs in solution.core_jobs.items():
		for ii, job in enumerate(jobs):
			if job.task.wcet + initial_step <= job.exec_window.stop - job.exec_window.start:
				neighbor = deepcopy(solution.core_jobs)

				# TODO : alter mapping & check (need to put core_tasks in solution again)

				neighbor[core][ii].exec_window = slice(job.exec_window.start + initial_step, job.exec_window.stop)
				core_jobs = schedule(neighbor, ordering)

				if _is_feasible(solution.problem.graph, core_jobs):
					candidates.add(Solution(solution.problem, core_jobs, solution.objective))

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

	if global_schedulability_test(problem):
		sched_check, ordering = algorithms[problem.config.params.algorithm]
		explored_domain: list[SortedSet[Solution]] = [SortedSet()]
		explored_domain[0].add(
			Solution(
				problem,
				schedule(mapping(problem.arch, problem.graph.apps, sched_check), ordering),
				objectives[problem.config.params.objective],
			),
		)

		while (candidates := get_neighbors(explored_domain[-1][0], ordering, sched_check)):
			#print("#" * 200)

			if explored_domain[-1][0].score <= candidates[0].score:
				explored_domain.append(candidates)
			else:
				break

		logging.info("Solution found for:\t" + str(problem.config.filepaths))

		#print(f"feasible ? {_is_feasible(problem.graph, explored_solutions[-1].core_jobs)}")
		"""
		for jobs in explored_solutions[-1].core_jobs.values():
			for job in jobs:
				print(job.pformat())
		"""

		# TODO : return first solution with the same score as last solution if more than one
		"""
		if 1 < len(explored_solutions):
			last_score = explored_solutions[-1][0]
			for i, sol in enumerate(resersed(explored_solutions[:-2])):
				if sol[0] < last_score:
					return resersed(explored_solutions[:-2])[i]
		"""

		return explored_domain[-1][0]
	else:
		return None
