#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from math import fsum

from graph_model import Job

from model import CoreJobMap, Ordering, Problem, Solution

from sortedcontainers import SortedSet  # type: ignore


# FUNCTIONS ###########################################################################################################


def global_schedulability_test(problem: Problem) -> bool:
	# EDF !
	security_margin = 0.9
	total_workload = fsum(task.workload for app in problem.graph.apps for task in app)

	if total_workload <= (sufficient_condition := sum(len(cpu) for cpu in problem.arch) * security_margin):
		return True
	else:
		raise RuntimeError(f"Total workload is {total_workload}, should not be higher than {sufficient_condition}.")


def _overlap_before(slice1: slice, slice2: slice) -> bool:
	"""
	typical case:
	slice1 |--------|
	slice2        |--------|

	edge case 1:
	slice1 |---------|
	slice2  |--------|

	edge case 2:
	slice1 |------|
	slice2 |---------|
	"""

	return (slice1.start < slice2.start and slice2.start < slice1.stop <= slice2.stop)\
		or (slice1.start == slice2.start and slice1.stop < slice2.stop)


def _overlap_after(slice1: slice, slice2: slice) -> bool:
	"""
	typical case:
	slice1      |--------|
	slice2 |--------|

	edge case 1:
	slice1 |--------|
	slice2 |-------|

	edge case 2:
	slice1    |------|
	slice2 |---------|
	"""

	return (slice2.start <= slice1.start < slice2.stop and slice2.stop < slice1.stop)\
		or (slice2.start < slice1.start and slice1.stop == slice2.stop)


def _inside(slice1: slice, slice2: slice) -> bool:
	"""
	typical case:
	slice1    |------|
	slice2 |------------|

	edge case:
	slice1 |------------|
	slice2 |------------|
	"""

	return slice2.start <= slice1.start and slice1.stop <= slice2.stop


def _intersect(slice1: slice, slice2: slice) -> bool:
	return _overlap_before(slice1, slice2) or _overlap_after(slice1, slice2)\
		or _inside(slice1, slice2) or _inside(slice2, slice1)


def _get_runtime(slices: list[slice]) -> int:
	_sum = 0

	for _slice in slices:
		_sum += _slice.stop - _slice.start

	return _sum


def _check_no_intersect(slices: list[slice]) -> None:
	if len(slices) < 2:
		return

	for i in range(len(slices) - 1):
		for ii in range(i + 1, len(slices)):
			if _intersect(slices[i], slices[ii]):
				raise RuntimeError(f"Error : slices '{slices[i]}' and '{slices[ii]}' intersect.")


def _get_intersect_slices(job: Job, c_jobs: SortedSet[Job]) -> list[slice]:
	# print("\t\t\t_get_intersect_slices")
	slices = []

	"""
	print("\t" * 4 + f"c_jobs ({len(c_jobs)}) :")
	for _job in c_jobs:
		print("\t" * 5 + _job.task.short() + " : " + str(_job.exec_window))
		for _slice in _job:
			print("\t" * 6 + str(_slice))
	"""

	for c_job in filter(lambda j: _intersect(job.exec_window, j.exec_window), c_jobs):
		# print("\t" * 4 + str(c_job.sched_window))
		for _slice in filter(lambda s: _intersect(job.exec_window, s), c_job):
			slices.append(_slice)  # check for partitions !

	"""
	print("\t" * 4 + "after :")
	for _slice in slices:
		print("\t" * 5 + str(_slice))
	"""

	_check_no_intersect(slices)  # check that the intersecting slices do not intersect between themselves

	return sorted(slices, key=lambda s: s.start)


def _get_slices(job: Job, c_jobs: SortedSet[Job]) -> list[slice]:
	# print("\t\t_get_slices")
	slices = _get_intersect_slices(job, c_jobs)

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
		if (runtime := _get_runtime(slices)) == job.task.wcet:
			job.execution.extend(slices)
		elif job.task.wcet < runtime:
			job.execution.extend(_generate_exec_slices(job, slices))
		else:
			return False

	return True


# ENTRY POINT #########################################################################################################


def schedule(core_jobs: CoreJobMap, problem: Problem, ordering: Ordering) -> Solution:
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
