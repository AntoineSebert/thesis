#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from math import fsum
from itertools import groupby

from arch_model import CoreJobMap

from graph_model import Job, Slice

from model import Problem

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
	total_workload = fsum(task.workload for app in problem.graph for task in app)

	if total_workload <= (sufficient_condition := sum(len(cpu) for cpu in problem.arch) * security_margin):
		return True
	else:
		raise RuntimeError(f"Total workload is {total_workload}, should not be higher than {sufficient_condition}.")


def _check_no_intersect(slices: list[Slice]) -> None:
	"""Ensures that all slices of a list are mutually exclusive.

	Parameters
	----------
	slices : list[Slice]
		A list of slices.

	Raises
	------
	RuntimeError
		If the workload carried by the problem is greater than the sufficient condition.
	"""

	#print("\n" + ("\t" * 4) + "_check_no_intersect")

	if len(slices) < 2:
		return

	for i in range(len(slices) - 1):
		for ii in range(i + 1, len(slices)):
			if slices[i].intersect(slices[ii]):
				raise RuntimeError(f"slices '{slices[i]}' and '{slices[ii]}' are not disjoint.")


def _get_intersecting_slices(target_job: Job, jobs: SortedSet[Job]) -> list[Slice]:
	"""Creates a list of slices from a set of jobs intersecting with the scheduling window of a job.

	Parameters
	----------
	slices : list[Slice]
		A list of slices.

	Returns
	-------
	list[Slice]
		A sorted list of slices.
	"""

	#print("\n" + ("\t" * 3) + "_get_intersect_slices")

	slices: list[Slice] = []

	"""
	print("\t" * 4 + f"jobs ({len(jobs)}) :")
	for job in jobs:
		print("\t" * 5 + job.task.short() + " : " + str(job.exec_window))
		for _slice in job:
			print("\t" * 6 + str(_slice))
	"""
	intersect = lambda s1, s2: s1.start < s2.stop and s2.start < s1.stop

	for job in filter(lambda job: intersect(job.exec_window, target_job.exec_window), jobs):
		# print("\t" * 4 + str(c_job.sched_window))
		for _slice in filter(lambda s: s.intersect(target_job.exec_window), job):
			slices.append(_slice)  # check for partitions !

	"""
	print("\t" * 4 + "after :")
	for _slice in slices:
		print("\t" * 5 + str(_slice))
	"""

	_check_no_intersect(slices)  # check that the intersecting slices do not intersect between themselves

	return sorted(slices, key=lambda s: s.start)


def _consume_leading_space(job: Job, start: int, first_start: int, job_slices: list[Slice], wcet: int) -> tuple[int, list[Slice]]:
	#print("\n" + ("\t" * 3) + "_consume_leading_space")

	if start < first_start and 0 < (space := first_start - start):
		if wcet <= space:
			job_slices.append(Slice(job, start, start + wcet))
			#print(str(job_slices[-1]))

			return (0, job_slices)
		else:
			job_slices.append(Slice(job, start, start + space))
			#print(str(job_slices[-1]))

			return (wcet - space, job_slices)
	else:
		return (wcet, job_slices)


def _consume_space(job: Job, slices: list[Slice], job_slices: list[Slice], remaining: int) -> tuple[int, list[Slice]]:
	#print("\n" + ("\t" * 3) + "_consume_space")

	for i in range(len(slices) - 1):
		if slices[i].stop < slices[i + 1].start and 0 < (space := slices[i + 1].start - slices[i].stop):
			if remaining <= space:
				job_slices.append(Slice(job, slices[i].stop, slices[i].stop + remaining))
				#print(str(job_slices[-1]))

				return (0, job_slices)
			else:
				job_slices.append(Slice(job, slices[i].stop, slices[i].stop + space))
				#print(str(job_slices[-1]))
				remaining -= space

	return (remaining, job_slices)


def _consume_trailing_space(job: Job, stop: int, last_stop: int, job_slices: list[Slice], remaining: int) -> list[Slice]:
	#print("\n" + ("\t" * 3) + "_consume_trailing_space")

	if last_stop < stop and 0 < (space := stop - last_stop):
		if remaining <= space:
			job_slices.append(Slice(job, last_stop, last_stop + remaining))
			#print(str(job_slices[-1]))

	return job_slices


def _get_slices(job: Job, jobs: SortedSet[Job]) -> list[Slice]:
	"""Gets the slices those total time is equal to the WCET of a job and that do not intersect with a set of jobs.

	Parameters
	----------
	job : Job
		A job to get execution slices for.
	jobs : SortedSet[Job]
		A set of jobs.

	Returns
	-------
	list[Slice]
		A list of execution slices for a job.

	Raises
	------
	RuntimeError
		If there is not enough free space within to schedule the job within its schedulign window.
	"""

	#print("\n" + ("\t" * 2) + "_get_slices")

	slices = _get_intersecting_slices(job, jobs)
	start = job.exec_window.start
	wcet = job.task.wcet

	if not slices:
		return [Slice(job, start, start + wcet)]

	remaining, job_slices = _consume_leading_space(job, start, slices[0].start, [], wcet)

	if remaining == 0:
		return job_slices

	remaining, job_slices = _consume_space(job, slices, job_slices, remaining)

	if remaining == 0:
		return job_slices
	else:
		return _consume_trailing_space(job, job.exec_window.stop, slices[-1].stop, job_slices, remaining)


def _generate_exec_slices(job: Job, slices: list[Slice]) -> list[Slice]:
	"""Creates potential execution slices for a job.

	Parameters
	----------
	job : Job
		A job to create execution slices for.
	slices : list[Slice]
		A list of potential execution slices.

	Returns
	-------
	potential_slices : list[Slice]
		The execution slices that are suitable for the executino of the job.
	"""

	#print("\n" + ("\t" * 2) + "_generate_exec_slices")

	potential_slices = []
	target_runtime = job.task.wcet

	# take slices until wcet has been all done (mind last slice might not be complete !)
	for _slice in slices:
		if target_runtime <= len(_slice):
			potential_slices.append(Slice(job, _slice.start, _slice.start + target_runtime))

			break
		else:
			potential_slices.append(_slice)
			target_runtime -= len(_slice)
	"""
	print("\t" * 3 + f"potential_slices ({len(potential_slices)}) :")
	for _slice in potential_slices:
		print("\t" * 4 + str(_slice))
	"""

	return potential_slices

# ENTRY POINT #########################################################################################################


def schedule(core_jobs: CoreJobMap, ordering: Ordering) -> CoreJobMap:
	"""Schedules a problem into a solution.

	Parameters
	----------
	core_jobs : CoreJobMap
		A map of cores to a set of jobs.
	ordering : Ordering
		An ordering algorithm, like EDF or RM.

	Returns
	-------
	core_jobs : CoreJobMap
		...

	Raises
	------
	RuntimeError
		If the execution slices for a job from set of jobs associated with a core could be all created.
	"""

	#print("/" * 200)
	for core, jobs in core_jobs.items():
		jobs = ordering(jobs)
		_key = lambda j: j.task.criticality

		for crit, _jobs in groupby(sorted(jobs, key=_key, reverse=True), key=_key):
			for job in _jobs:
				slices = _get_slices(job, jobs)
				"""
				print("\t" * 2 + f"exec slices ({len(slices)}) :")
				for _slice in slices:
					print("\t" * 4 + str(_slice))
				"""

				job.execution.update(_generate_exec_slices(job, slices))
				"""
				if task.criticality < problem.graph.max_criticality():
					raise NotImplementedError  # backtrack
				else:
					raise RuntimeError(f"Initial scheduling failed with task : '{task.app.name}/{task.id}'.")
				"""

	return core_jobs
