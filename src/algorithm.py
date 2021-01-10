#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from __future__ import annotations

from math import fsum
from typing import Callable, Collection, Iterable

from arch_model import Core

from graph_model import Job, Task


# CLASSES AND TYPE ALIASES ############################################################################################


class SchedAlg:
	security_margin: int
	name: str
	short: str


"""Scheduling check, returns the sufficient condition."""
SchedCheck = Callable[[Collection[Task], Collection[Core]], bool]
Ordering = Callable[[Iterable[Job]], Iterable[Job]]

"""
class scheduler/ordinator
	attr
		sec margin
		name
	members
		global sched check
		local sched check
		ordering
"""

"""Algorithms for scheduling, containing the sufficient condition, an ordering function."""
algorithms: dict[str, tuple[SchedCheck, Ordering]] = {
	"edf": (
		lambda tasks, cores: fsum(task.workload for task in tasks) <= len(cores) * 0.9,
		lambda jobs: sorted(jobs, key=lambda job: job.sched_window.stop),
	),
	"rm": (
		lambda tasks, cores: fsum(task.workload for task in tasks) <= len(cores) * 0.9 * (len(tasks) * (2**(1 / len(tasks)) - 1)),
		lambda jobs: sorted(jobs, key=lambda job: job.task.period),
	),
}
