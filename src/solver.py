#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging
from copy import deepcopy
from typing import Optional

from algorithm import algorithms

from arch_model import Core, CoreJobMap

from graph_model import Graph, Job

from mapper import alter_mapping, get_alteration_possibilities, mapping

from model import Problem, Solution

from objective import objectives

from scheduler import schedule

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


def _try_generate_neighbor(source: Solution, core: Core, job: Job, job_index: int) -> Optional[Solution]:
	print("\t\t_try_generate_neighbor")

	neighbor: CoreJobMap = {deepcopy(core): deepcopy(jobs) for core, jobs in source.core_jobs.items()}
	initial_step = source.problem.config.params.initial_step
	switch_time = source.problem.config.params.switch_time

	neighbor[core][job_index].exec_window = slice(job.exec_window.start + initial_step, job.exec_window.stop)

	if source.possibilities:
		if alter_mapping(source.possibilities, source.algorithm, neighbor):
			"""
			for cpu in source.problem.arch:
				for core in cpu:
					if core.tasks:
						neighbor[core] = SortedSet(job for task in core for job in task)
			"""
		else:
			raise RuntimeError("Re-mapping unschedulable")

	core_jobs = schedule(neighbor, source.algorithm, switch_time)

	if _is_feasible(source.problem.graph, core_jobs):
		return Solution(source.problem, core_jobs, source.objective, source.algorithm, source.possibilities)
	else:
		return None


def get_neighbors(solution: Solution) -> list[Solution]:
	"""Gets the feasible scheduled neighbors (candidates) of a Solution.

	Parameters
	----------
	solution : Solution
		A target Solution.

	Returns
	-------
	candidates : list[Solution]
		A list of candidates, may be empty.
	"""

	print("\tget_neighbors")

	candidates: list[Solution] = []
	initial_step = solution.problem.config.params.initial_step

	for core, jobs in solution.core_jobs.items():
		for ii, job in enumerate(jobs):
			#print(len(jobs), ii)

			if job.task.wcet + initial_step <= job.exec_window.stop - job.exec_window.start:
				if (result := _try_generate_neighbor(solution, core, job, ii)) is not None:
					candidates.append(result)

	return sorted(candidates)


def _optimise(initial_solution: Solution) -> list[list[Solution]]:
	print("_optimize")

	explored_domain: list[list[Solution]] = [[]]
	explored_domain[0].append(initial_solution)

	while candidates := get_neighbors(explored_domain[-1][0]):
		"""
		print(f"fittest candidate: {int(candidates[0].score)}")
		print(f"least fit candidate: {int(candidates[-1].score)}")
		print(f"target score: {int(explored_domain[-1][0].score)}")
		print(f"target offset sum: {explored_domain[-1][0].offset_sum}")
		"""

		if initial_solution.objective.comp(candidates[0].score, explored_domain[-1][0].score) or explored_domain[-1][0].score == candidates[0].score:
			explored_domain.append(candidates)
		else:
			"""
			for jobs in explored_domain[-1][0].core_jobs.values():
				for job in jobs:
					print(job.pformat())
			"""

			break

	"""
	for generation in explored_domain:
		print(_svg_format(generation[0]))
	"""

	return explored_domain


# ENTRY POINT #########################################################################################################


@timed_callable("Solving the problem...")
def solve(problem: Problem) -> list[Solution]:
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

	# must be done before call to get_alteration_possibilities()
	core_jobs = mapping(problem.arch, problem.graph.apps, _algorithm)
	possibilities = get_alteration_possibilities(problem.arch, problem.graph)

	initial_solution = Solution(
		problem,
		schedule(core_jobs, _algorithm, problem.config.params.switch_time),
		objectives[problem.config.params.objective],
		_algorithm,
		possibilities,
	)

	#print(initial_solution.offset_sum)
	solutions = _optimise(initial_solution)

	logging.info("Solution found for:\t" + str(problem.config.filepaths))

	final = [initial_solution]
	final.extend([generation[0] for generation in solutions])

	return final #[solutions[-1][0]]
