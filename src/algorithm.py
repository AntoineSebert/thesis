#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from __future__ import annotations

from dataclasses import dataclass
from math import fsum
from typing import Callable, Iterable, Optional, Sequence

from arch_model import Architecture, Core

from graph_model import Graph, Job, Task


# FUNCTIONS ###########################################################################################################

def _local_check_edf(cores: Sequence[Core], tasks: Sequence[Task], security_margin: float) -> SchedCheckResult:
	"""Determines the schedulability of a problem with the EDF algorithm.

	Parameters
	----------
	problem : Problem
		A `Problem`.
	"""

	return _local_check(fsum(task.workload for task in tasks), len(cores) * security_margin)


def _local_check_rm(cores: Sequence[Core], tasks: Sequence[Task], security_margin: float) -> SchedCheckResult:
	"""Determines the schedulability of a problem with the RM algorithm.

	Parameters
	----------
	problem : Problem
		A `Problem`.
	"""

	return _local_check(
		fsum(task.workload for task in tasks),
		len(cores) * security_margin * (len(tasks) * (2**(1 / len(tasks)) - 1)),
	)


def _local_check(total_workload: float, sufficient_condition: float) -> SchedCheckResult:
	if total_workload > sufficient_condition:
		return (total_workload, sufficient_condition)
	else:
		return None

# CLASSES AND TYPE ALIASES ############################################################################################


"""Scheduling check, returns the sufficient condition."""
SchedCheckResult = Optional[tuple[float, float]]
SchedChecker = Callable[[Sequence[Core], Sequence[Task], float], SchedCheckResult]
Scheduler = Callable[[Iterable[Job]], Iterable[Job]]


@dataclass
class SchedAlgorithm:
	name: str
	security_margin: float
	local_scheduling_check: SchedChecker
	scheduler: Scheduler

	def __call__(self: SchedAlgorithm, jobs: Iterable[Job]) -> Iterable[Job]:
		return self.scheduler(jobs)

	def global_scheduling_check(self: SchedAlgorithm, arch: Architecture, graph: Graph) -> SchedCheckResult:
		return self.local_scheduling_check(
			[core for cpu in arch for core in cpu], [task for app in graph for task in app], self.security_margin,
		)


# DATA ################################################################################################################

algorithms: dict[str, SchedAlgorithm] = {
	"edf": SchedAlgorithm(
		"Earliest Deadline First",
		0.9,
		_local_check_edf,
		lambda jobs: sorted(jobs, key=lambda job: job.sched_window.stop),
	),
	"rm": SchedAlgorithm(
		"Rate monotonic",
		0.9,
		_local_check_rm,
		lambda jobs: sorted(jobs, key=lambda job: job.task.period),
	),
}
