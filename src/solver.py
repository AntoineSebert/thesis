#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging

from graph_model import Graph

from mapper import mapping

from model import algorithms, objectives, Mapping, Problem, Solution

from scheduler import schedule

from timed import timed_callable


# FUNCTIONS ###########################################################################################################

def get_neighbors(solution, algorithm) -> list[Graph]:
	candidates = []

	for task in solution:
		for job in task.jobs:
			if 10 <= job.max_offset - job.offset:
				neighbor = solution.copy()
				neighbor.tasks[task].jobs[job].offset += 10

				if is_feasible(neighbor, algorithm):
					candidates.add(neighbor)

	return candidates


def is_feasible(candidate, algorithm) -> bool:
	schedule(candidate, algorithm)

	for task in candidate.tasks:
		for job in task.jobs:
			if deadline_miss(task, job):
				return False

	for app in filter(apps, lambda a: a.ordered):
		for task in app.tasks:
			if order_miss(app, task):
				return False

	return True


# optimization --------------------------------------------------------------------------------------------------------

def _optimization(problem: Problem, feasible_solution: dict) -> Solution:
	return Solution(problem, 0, feasible_solution)


# feasible scheduling -------------------------------------------------------------------------------------------------


def _feasible_scheduling(initial_solution: Mapping) -> Mapping:
	# check if parent
	return initial_solution


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

	initial_map = mapping(problem.arch, problem.graph.apps, sched_check)
	initial_solution = schedule(initial_map, problem.graph.max_criticality(), problem.config.params.algorithm)
	feasible_solution = _feasible_scheduling(initial_solution)
	extensible_solution = _optimization(problem, feasible_solution)

	"""
	current = schedule(initial_mapping(arch, apps, sched_check), ordering)

	while True:
		candidates = get_neighbors(current_solution, ordering)

		if not candidates:
			break

		best_candidate = max(candidates, lambda c: c.score)

		if current.score <= best_candidate.score:
			current = best_candidate
	"""
	logging.info("Solution found for:\t" + str(problem.config.filepaths))

	return extensible_solution
