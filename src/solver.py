#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from copy import deepcopy

from graph_model import Graph, Job

from arch_model import CoreJobMap

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


def _modify_job(core_jobs: CoreJobMap, job: Job, initial_step: int) -> None:
	for jobs in core_jobs.values():
		for _job in jobs:
			# TODO : check if app, task and sched_windows correspond instead
			if _job.task is job.task and _job.sched_window == job.sched_window:
				_job.exec_window = slice(_job.exec_window.start + initial_step, _job.exec_window.stop)
				if (_job.exec_window.stop - _job.exec_window.start) < _job.task.wcet:
					raise RuntimeError(f"{_job.exec_window=} // {_job.task.wcet}")

	return core_jobs


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

	#print("=" * 200)
	candidates = []
	initial_step = solution.problem.config.params.initial_step

	#print("candidates search...")
	for core, jobs in solution.core_jobs.items():
		for ii, job in enumerate(jobs):
			if job.task.wcet + initial_step <= job.exec_window.stop - job.exec_window.start:
				#print("model : " + job.short())
				neighbor = deepcopy(solution.core_jobs)
				#print(neighbor[core][ii].short())

				core_jobs = schedule(_modify_job(neighbor, job, initial_step), ordering)

				if _is_feasible(solution.problem.graph, core_jobs):
					#print(f"\tadding cand {len(candidates)}.")
					candidates.append(Solution(solution.problem, core_jobs))
					#print(f"\tcand feasible ? { _is_feasible(solution.problem.graph, candidates[-1].core_jobs)}")

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
		explored_solutions: list[Solution] = [Solution(problem, schedule(core_jobs, ordering))]

		while (candidates := get_neighbors(explored_solutions[-1], ordering, sched_check)):
			#print(len(explored_solutions))
			best_candidate = max(candidates, key=lambda c: empty_space(c))

			# either < or <=, should be ideally <= to explore full search space
			if empty_space(explored_solutions[-1]) <= (best_score := empty_space(best_candidate)):
				explored_solutions.append(best_candidate)
				# print(f"total offsets : {sum((job.offset for jobs in best_candidate.core_jobs.values() for job in jobs), start=0)} // score : {best_score}")
			else:
				break

		logging.info("Solution found for:\t" + str(problem.config.filepaths))

		#print(f"feasible ? {_is_feasible(problem.graph, explored_solutions[-1].core_jobs)}")
		"""
		for jobs in explored_solutions[-1].core_jobs.values():
			for job in jobs:
				print(job.pformat())
		"""

		return explored_solutions[-1] # return first solution with the same score as last solution if more than one
	else:
		return None
