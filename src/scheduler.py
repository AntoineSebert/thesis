#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from functools import reduce
from math import fsum

from graph_model import Job

from model import CoreJobMap, Ordering, Problem, Solution

from sortedcontainers import SortedSet  # type: ignore


# FUNCTIONS ###########################################################################################################


def global_schedulability_test(problem: Problem) -> bool:
	"""Determines the schedulability of a problem with the EDF algorithm with a security margin of 0.9.

	Parameters
	----------
	problem : Problem
		A `Problem`.

	Returns
	-------
	bool
		Returns `True` if the workload carried by the problem is less or equal to the sufficient condition, or `False` otherwise.

	Raises
	------
	RuntimeError
		If the workload carried by the problem is greater than the sufficient condition.
	"""

	security_margin = 0.9
	total_workload = fsum(task.workload for app in problem.graph.apps for task in app)

	if total_workload <= (sufficient_condition := sum(len(cpu) for cpu in problem.arch) * security_margin):
		return True
	else:
		raise RuntimeError(f"Total workload is {total_workload}, should not be higher than {sufficient_condition}.")


def _overlap_before(slice1: slice, slice2: slice) -> bool:
	"""Checks if a slice is partially overlaps before another.

	typical case:
		slice1 |--------|
		slice2        |--------|

	edge case 1:
		slice1 |---------|
		slice2  |--------|

	edge case 2:
		slice1 |------|
		slice2 |---------|

	Parameters
	----------
	slice1, slice2 : slice
		A pair of slices.

	Returns
	-------
	bool
		Returns `True` if the first slice partially overlaps before the second.
	"""

	return (slice1.start < slice2.start and slice2.start < slice1.stop <= slice2.stop)\
		or (slice1.start == slice2.start and slice1.stop < slice2.stop)


def _overlap_after(slice1: slice, slice2: slice) -> bool:
	"""Checks if a slice is partially overlaps after another.

	typical case:
	slice1      |--------|
	slice2 |--------|

	edge case 1:
	slice1 |--------|
	slice2 |------|

	edge case 2:
	slice1    |------|
	slice2 |---------|

	Parameters
	----------
	slice1, slice2 : slice
		A pair of slices.

	Returns
	-------
	bool
		Returns `True` if the first slice partially overlaps after the second.
	"""

	return (slice2.start <= slice1.start < slice2.stop and slice2.stop < slice1.stop)\
		or (slice2.start < slice1.start and slice1.stop == slice2.stop)


def _inside(slice1: slice, slice2: slice) -> bool:
	"""Checks if a slice is within another.

	typical case:
	slice1    |------|
	slice2 |------------|

	Parameters
	----------
	slice1, slice2 : slice
		A pair of slices.

	Returns
	-------
	bool
		Returns `True` if the first slice is within the second.
	"""

	return slice2.start < slice1.start and slice1.stop < slice2.stop


def _intersect(slice1: slice, slice2: slice) -> bool:
	"""Checks if two slices intersect whatsoever.

	Parameters
	----------
	slice1, slice2 : slice
		A pair of slices.

	Returns
	-------
	bool
		Returns `True` if the slices intersect.
	"""

	return slice1 == slice2 or _overlap_before(slice1, slice2) or _overlap_after(slice1, slice2)\
		or _inside(slice1, slice2) or _inside(slice2, slice1)


def _check_no_intersect(slices: list[slice]) -> None:
	"""Ensures that all slices of a list are mutually exclusive.

	Parameters
	----------
	slices : list[slice]
		A list of slices.

	Raises
	------
	RuntimeError
		If the workload carried by the problem is greater than the sufficient condition.
	"""

	if len(slices) < 2:
		return

	for i in range(len(slices) - 1):
		for ii in range(i + 1, len(slices)):
			if _intersect(slices[i], slices[ii]):
				raise RuntimeError(f"Error : slices '{slices[i]}' and '{slices[ii]}' intersect.")


def _get_intersecting_slices(target_job: Job, jobs: SortedSet[Job]) -> list[slice]:
	"""Creates a list of slices from a set of jobs intersecting with the scheduling window of a job.

	Parameters
	----------
	slices : list[slice]
		A list of slices.

	Returns
	-------
	list[slice]
		A sorted list of slices.
	"""

	# print("\t\t\t_get_intersect_slices")
	slices: list[slice] = []

	"""
	print("\t" * 4 + f"c_jobs ({len(c_jobs)}) :")
	for _job in c_jobs:
		print("\t" * 5 + _job.task.short() + " : " + str(_job.exec_window))
		for _slice in _job:
			print("\t" * 6 + str(_slice))
	"""

	for job in filter(lambda job: _intersect(target_job.sched_window, job.sched_window), jobs):
		# print("\t" * 4 + str(c_job.sched_window))
		for _slice in filter(lambda slice: _intersect(target_job.sched_window, slice), job):
			slices.append(_slice)  # check for partitions !

	"""
	print("\t" * 4 + "after :")
	for _slice in slices:
		print("\t" * 5 + str(_slice))
	"""

	_check_no_intersect(slices)  # check that the intersecting slices do not intersect between themselves

	return sorted(slices, key=lambda s: s.start)


def _get_slices(job: Job, jobs: SortedSet[Job]) -> list[slice]:
	"""Gets the slices those total time is equal to the WCET of a job and that do not intersect with a set of jobs.

	Parameters
	----------
	job : Job
		A job to get execution slices for.
	jobs : SortedSet[Job]
		A set of jobs.

	Returns
	-------
	list[slice]
		A list of execution slices for a job.

	Raises
	------
	RuntimeError
		If there is not enough free space within to schedule the job within its schedulign window.
	"""

	# print("\t\t_get_slices")
	slices = _get_intersecting_slices(job, jobs)

	if not slices:
		return [slice(job.exec_window.start, job.exec_window.start + job.task.wcet)]

	job_slices = []
	remaining = job.task.wcet

	# eventual leading space
	if job.exec_window.start < slices[0].start:
		if remaining <= (space := slices[0].start - job.exec_window.start):
			return [slice(job.exec_window.start, job.exec_window.start + remaining)]
		else:
			job_slices.append(slice(job.exec_window.start, job.exec_window.start + space))
			remaining -= space

	for i in range(len(slices) - 1):
		if 0 < (space := slices[i + 1].start - slices[i].stop):
			if remaining <= space:
				job_slices.append(slice(slices[i].stop, slices[i].stop + remaining))

				return job_slices
			else:
				job_slices.append(slice(slices[i].stop, slices[i].stop + space))
				remaining -= space

	# eventual following space
	if slices[-1].stop < job.exec_window.stop:
		if remaining <= (space := job.exec_window.stop - slices[-1].stop):
			job_slices.append(slice(slices[-1].stop, slices[-1].stop + space))

			return job_slices
		else:
			raise RuntimeError(f"Not enough running time to schedule {job.short()}.")

	return job_slices


def _generate_exec_slices(job: Job, slices: list[slice]) -> list[slice]:
	"""Creates potential execution slices for a job.

	Parameters
	----------
	job : Job
		A job to create execution slices for.
	slices : list[slice]
		A list of potential execution slices.

	Returns
	-------
	j_slices : list[slice]
		The execution slices that are suitable for the executino of the job.
	"""

	# print("\t\t_generate_exec_slices")
	j_slices = []
	target_runtime = job.task.wcet

	# take slices until wcet has been all done (mind last slice might not be complete !)
	for _slice in slices:
		if target_runtime <= _slice.stop - _slice.start:
			j_slices.append(slice(_slice.start, _slice.start + target_runtime))

			break
		else:
			j_slices.append(_slice)

		target_runtime -= _slice.stop - _slice.start

	return j_slices


def _create_execution_slices(jobs: SortedSet[Job]) -> bool:
	"""Creates execution slices for a set of jobs.

	Parameters
	----------
	jobs : SortedSet[Job]
		A set of jobs.

	Returns
	-------
	bool
		Returns `True` if all jobs have been scheduled, or `False` otherwise.
	"""

	"""
	print("\t_schedule_task " + "=" * 140)

	print("\t" * 2 + f"c_jobs ({len(jobs)}) :")
	for _job in jobs:
		print("\t" * 3 + _job.task.short() + " : " + str(_job.exec_window))
		for _slice in _job:
			print("\t" * 4 + str(_slice))
	"""

	for job in jobs:
		slices = _get_slices(job, jobs)

		# checks if enough runtime
		if (runtime := reduce(lambda s1, s2: (s1.stop - s1.start) + (s2.stop - s2.start), slices, 0)) == job.task.wcet:
			job.execution.extend(slices)
		elif job.task.wcet < runtime:
			job.execution.extend(_generate_exec_slices(job, slices))
		else:
			return False

	return True


# ENTRY POINT #########################################################################################################


def schedule(core_jobs: CoreJobMap, problem: Problem, ordering: Ordering) -> Solution:
	"""Schedules a problem into a solution.

	Parameters
	----------
	core_jobs : CoreJobMap
		A map of cores to a set of jobs.
	problem : Problem
		A problem to schedule.
	ordering : Ordering
		An ordering algorithm, like EDF or RM.

	Returns
	-------
	Solution
		A scheduled solution.

	Raises
	------
	RuntimeError
		If the execution slices for a job from set of jobs associated with a core could be all created.
	"""

	# print("/" * 200)
	for core, jobs in core_jobs.items():
		jobs = ordering(jobs)

		if not _create_execution_slices(jobs):
			raise RuntimeError(f"Initial scheduling failed with core : '{core.short()}'.")
			"""
			if task.criticality < problem.graph.max_criticality():
				raise NotImplementedError  # backtrack
			else:
				raise RuntimeError(f"Initial scheduling failed with task : '{task.app.name}/{task.id}'.")
			"""

	return Solution(problem, core_jobs)
