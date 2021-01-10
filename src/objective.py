#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from __future__ import annotations

from dataclasses import dataclass
from operator import gt, lt
from typing import Callable, Union

from model import Solution


# OBJECTIVE FUNCTIONS #################################################################################################

def cumulated_empty_space(solution: Solution) -> Score:
	total_running = 0

	for jobs in solution.core_jobs.values():
		if jobs:
			all_sorted_slices = sorted(_slice for job in jobs for _slice in job)

			if len(all_sorted_slices) == 1:
				total_running += len(all_sorted_slices[0])
			else:
				running_time = 0

				for _slice in all_sorted_slices:
					running_time += len(_slice)

				total_running += running_time

	return (len(solution.core_jobs) * solution.problem.graph.hyperperiod) - total_running


def normal_distr_empty_space(solution: Solution) -> Score:
	pass


def min_app_delay(solution: Solution) -> Score:
	total_delay = 0

	for app in solution.problem.graph:
		# get app length
		# if app.order
			# assert len(task) for all tasks is the same
		# for each app activation
			# get delay
		if app.order:
			total_delay += app[-1].jobs[-1].execution[-1].stop - app[0].jobs[0].execution[0].start
		else:
			earliest_start = solution.problem.graph.hyperperiod
			latest_stop = 0

			for task in app:
				if task.jobs[0].execution[0].start < earliest_start:
					earliest_start = task.jobs[0].execution[0].start

				if latest_stop < task.jobs[-1].execution[-1].stop:
					latest_stop = task.jobs[-1].execution[-1].stop

			assert(earliest_start < latest_stop)
			total_delay += latest_stop - earliest_start

	return total_delay


# CLASSES AND TYPE ALIASES ############################################################################################

Score = Union[int, float]


Scoring = Callable[[Solution], Score]


@dataclass
class Objective:
	"""Objective functions that assign a score to a feasible solution."""

	name: str
	comp: Callable[[Solution, Solution, bool]]
	function: Scoring

	def __call__(self: Objective, solution: Solution) -> Score:
		return self.function(solution)


# DATA ################################################################################################################

"""Objectives and descriptions."""
objectives: dict[str, Objective] = {
	"cumulated_free": Objective("cumulated empty space", gt, cumulated_empty_space),
	"min_e2e_app_del": Objective("minimal end-to-end application delay", lt, min_app_delay),
	"nrml_dist_free": Objective("normal distribution of free space", lt, normal_distr_empty_space),  # is it really lt ?
}
