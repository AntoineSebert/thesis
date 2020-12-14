#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from itertools import groupby

from graph_model import Criticality, Job, Task

from model import Core, CoreJobMap, CoreTaskMap, ProcAppMap, SortedMap, algorithms

from sortedcontainers import SortedSet  # type: ignore


# FUNCTIONS ###########################################################################################################


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


def _get_intersect_slices(job: Job, c_jobs: SortedSet[Job]) -> list[slice]:
	slices = []

	for c_job in filter(lambda j: _intersect(job.exec_window, j.exec_window), c_jobs):
		for _slice in filter(lambda s: _intersect(job.exec_window, s), c_job):
			slices.append(_slice)  # check for partitions !

	_check_no_intersect(slices)  # check that the intersecting slices do not intersect between themselves

	return sorted(slices, key=lambda s: s.start)


def _check_no_intersect(slices: list[slice]) -> None:
	if len(slices) < 2:
		return

	for i in range(len(slices) - 1):
		for ii in range(i + 1, len(slices)):
			if _intersect(slices[i], slices[ii]):
				raise RuntimeError(f"Error : slices '{slices[i]}' and '{slices[ii]}' intersect.")


def _get_slices(job: Job, c_jobs: SortedSet[Job]) -> list[slice]:
	slices = _get_intersect_slices(job, c_jobs)

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

	# eventual leading space
	if slices[-1].stop < job.exec_window.stop:
		if remaining <= (space := job.exec_window.stop - slices[-1].stop):
			job_slices.append(slice(slices[-1].stop, slices[-1].stop + space))
			return job_slices
		else:
			raise RuntimeError(f"Not enough running time to schedule {job.short()}.")

	return job_slices


def _generate_exec_slices(job: Job, slices: list[slice]) -> list[slice]:
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


def _schedule_task(task: Task, core: Core, c_jobs: SortedSet[Job]) -> bool:
	if len(c_jobs) == 0:
		for job in task:
			job.execution.append(slice(job.exec_window.start, job.exec_window.start + task.wcet))
			c_jobs.add(job)
	else:
		for job in task:
			slices = _get_slices(job, c_jobs)
			# check if enough runtime
			if (runtime := _get_runtime(slices)) == task.wcet:
				job.execution.extend(slices)
			elif task.wcet < runtime:
				job.execution.extend(_generate_exec_slices(job, slices))
			else:
				return False

			c_jobs.add(job)

	return True


def _order_task_cores(initial_mapping: ProcAppMap, algorithm: str) -> SortedMap:
	_, ordering = algorithms[algorithm]

	task_core: dict[Task, Core] = {}
	for _apps, core_tasks in initial_mapping.values():
		for core, tasks in core_tasks.items():
			for task in tasks:
				task_core[task] = core

	crit_ordered_task_core: SortedMap = {
		app.criticality: {} for apps, core_tasks in initial_mapping.values() for app in apps
	}

	for apps, _core_tasks in initial_mapping.values():
		for crit, apps in groupby(reversed(apps), lambda a: a.criticality):
			for app in SortedSet(apps, key=lambda a: a.order):
				# schedulign algorithm
				for task in ordering(app) if app.order else app.tasks:
					crit_ordered_task_core[crit][task] = task_core[task]

	return crit_ordered_task_core


# ENTRY POINT #########################################################################################################


def schedule(initial_mapping: ProcAppMap, max_crit: Criticality, algorithm: str) -> CoreJobMap:
	crit_ordered_task_core = _order_task_cores(initial_mapping, algorithm)
	cotc_done: SortedMap = {app.criticality: {} for apps, core_tasks in initial_mapping.values() for app in apps}
	core_jobs: CoreJobMap = {
		core: SortedSet() for app, core_tasks in initial_mapping.values() for core in core_tasks.keys()
	}

	for crit, ordered_task_core in reversed(crit_ordered_task_core.items()):
		for task, core in ordered_task_core.items():
			if not _schedule_task(task, core, core_jobs[core]):
				if crit < max_crit:
					raise NotImplementedError  # backtrack
				else:
					raise RuntimeError(f"Initial scheduling failed with task : '{task.app.name}/{task.id}'.")

			cotc_done[crit][task] = core

	return core_jobs
