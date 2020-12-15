#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

import logging

from graph_model import Graph

from mapper import mapping

from model import algorithms, objectives, CoreJobMap, Problem, Solution

from scheduler import schedule

from timed import timed_callable


# FUNCTIONS ###########################################################################################################

def get_neighbors(solution: Solution, algorithm) -> list[Graph]:
	candidates = []

	for app in solution.problem.graph.apps:
		for task in app:
			for job in task:
				if 10 <= job.local_deadline - job.offset:
					neighbor = solution.copy()
					neighbor.tasks[task].jobs[job].offset += solution.problem.config.params.initial_step

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


def _feasible_scheduling(initial_solution: CoreJobMap) -> CoreJobMap:
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
	initial_solution = schedule(mapping(problem.arch, problem.graph.apps, sched_check), problem, ordering)

	"""
	feasible_solution = _feasible_scheduling(initial_solution)
	extensible_solution = _optimization(problem, feasible_solution)
	"""

	current = initial_solution

	while (candidates := get_neighbors(current, ordering)):
		best_candidate = max(candidates, lambda c: c.score)

		if current.score <= best_candidate.score:
			current = best_candidate

	logging.info("Solution found for:\t" + str(problem.config.filepaths))

	return current
