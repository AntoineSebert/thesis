#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from __future__ import annotations


from collections.abc import Iterator, Reversible, Sequence, Set
from dataclasses import dataclass, field
from enum import IntEnum, unique
from functools import cached_property, total_ordering
from math import fsum
from typing import NamedTuple, Type

from sortedcontainers import SortedSet  # type: ignore


# CLASSES #############################################################################################################


@unique
class Criticality(IntEnum):
	"""Task criticality level

	dyn_0: null
	sta_1: minimal E2E delay
	sta_2: bounded jitter
	sta_3: 0 jitter
	sta_4: 0 jitter and minimal completion time
	"""

	dyn_0 = 0
	sta_1 = 1
	sta_2 = 2
	sta_3 = 3
	sta_4 = 4


@dataclass
@total_ordering
class Job(Set, Reversible):
	"""Represents an execution slice of a task.

	Attributes
	----------
	task : Task
		The task the job belongs to.
	sched_window : slice
		The window scheduling time, representing (activation_time, activation_time + deadline).
	exec_window : slice
		The window execution time, representing (activation_time + offset, activation_time + local_deadline).
	execution : list[slice]
		Set of execution slices.
	"""

	task: Task
	sched_window: slice
	exec_window: slice
	execution: list[slice] = field(default_factory=list)

	def duration(self: Job) -> int:
		"""Computes and caches the duration of the slice.
		Parameters
		----------
		self : Job
			The instance of `Job`.
		Returns
		-------
		int
			The duration of the job.
		"""

		return sum(_slice.stop - _slice.start for _slice in self.execution) if len(self.execution) != 0 else 0

	def offset(self: Job) -> int:
		"""The earliest start time within the execution window."""
		return self.exec_window.start - self.sched_window.start

	def local_deadline(self: Job) -> int:
		"""The local deadline within the execution window."""
		return self.exec_window.stop - self.sched_window.stop

	def has_miss(self: Job) -> bool:
		for _slice in self.execution:
			if self.exec_window.stop < _slice.start or self.exec_window.stop < _slice.stop:
				return True

		return False

	def __eq__(self: Job, other: object) -> bool:
		if isinstance(other, Job):
			return self.task == other.task and self.sched_window == other.sched_window
		else:
			return NotImplemented

	def __lt__(self: Job, other: object) -> bool:
		if isinstance(other, Job):
			return self.exec_window.start < other.exec_window.start
		else:
			return NotImplemented

	def __contains__(self: Job, item: object) -> bool:
		if isinstance(item, slice):
			return item in self.execution
		else:
			return NotImplemented

	def __iter__(self: Job) -> Iterator[slice]:
		return iter(self.execution)

	def __reversed__(self: Job) -> Iterator[slice]:
		return reversed(self.execution)

	def __len__(self: Job) -> int:
		return len(self.execution)

	def __hash__(self: Job) -> int:
		return hash(str(self.task) + str(self.exec_window) + str(self.sched_window) + str(self.execution))

	def short(self: Job) -> str:
		return f"{self.task.short()} [{self.sched_window.start} - {self.sched_window.stop}][{self.exec_window.start} - {self.exec_window.stop}]"

	def pformat(self: Job, level: int = 0) -> str:
		i = "\n" + ("\t" * level)
		ii = i + "\t"

		return (f"{i}job {{{ii}"
			f"task : {self.task.app.name} / {self.task.id};{ii}"
			f"exec_window : {self.exec_window} / {self.duration()};{ii}"
			f"execution {{" + "".join(f"{ii}\t{_slice};" for _slice in self.execution) + ii + "}" + i + "}")


@dataclass
@total_ordering
class Task(Set, Reversible):
	"""Represents a task.

	Attributes
	----------
	id : int
		The node id within an `App`.
	app : App
		The App to which the task belongs to.
	wcet : int
		The WCET of the node.
	period : int
		The period of the node.
	deadline : int
		The deadline of the node.
	criticality : Criticality
		The criticality level, [0; 4].
	jobs : SortedSet[Job]
		A set of n instances of the task, with n = int(wcet / hyperperiod).
	parent : Task
		A list of tasks to be completed before starting.
	"""

	id: int
	app: App
	wcet: int
	period: int
	deadline: int
	criticality: Criticality
	parent: Task = None
	jobs: SortedSet[Job] = field(default_factory=SortedSet)

	def __eq__(self: Task, other: object) -> bool:
		if isinstance(other, Task):
			return self.id == other.id and self.app == other.app
		else:
			return NotImplemented

	def __lt__(self: Task, other: object) -> bool:
		if isinstance(other, Task):
			return self.criticality < other.criticality
		else:
			return NotImplemented

	def __contains__(self: Task, item: object) -> bool:
		if isinstance(item, Job):
			return item.task is self and item in self.jobs
		else:
			return NotImplemented

	def __iter__(self: Task) -> Iterator[Job]:
		return iter(self.jobs)

	def __reversed__(self: Task) -> Iterator[Job]:
		return reversed(self.jobs)

	def __len__(self: Task) -> int:
		return len(self.jobs)

	def __hash__(self: Task) -> int:
		return hash(str(self.id) + self.app.name)

	def __new__(cls: Type[Task], id: int, app: App, wcet: int, period: int, deadline: int, criticality: Criticality) -> Task:
		self = super().__new__(cls)  # Must explicitly create the new object
		# Aside from explicit construction and return, rest of __new__ is same as __init__
		self.id = id
		self.app = app
		self.wcet = wcet
		self.period = period
		self.deadline = deadline
		self.criticality = criticality
		self.parent = None
		self.jobs = SortedSet()

		return self  # __new__ returns the new object

	def __getnewargs__(self: Task) -> tuple[int, App, int, int, int, Criticality]:
		# Return the arguments that *must* be passed to __new__
		return (self.id, self.app, self.wcet, self.period, self.deadline, self.criticality)

	def has_miss(self: Task) -> bool:
		for job in self:
			if job.has_miss():
				return True

		return False

	def check_execution_time(self: Task, hyperperiod: int) -> bool:
		"""Computes the total execution time of the task.

		Parameters
		----------
		self : Task
			The instance of `Task`.

		Returns
		-------
		bool
			The total execution time.
		"""

		return sum(job.duration() for job in self.jobs) == int(hyperperiod / self.period) * self.wcet

	@cached_property
	def workload(self: Task) -> float:
		"""Computes and caches the workload of the instance.

		Parameters
		----------
		self : Task
			The instance of `Task`.

		Returns
		-------
		float
			The workload of the task.
		"""

		return self.wcet / self.period

	def short(self: Task) -> str:
		return f"{self.app.name} / {self.id}"

	def pformat(self: Task, level: int = 0) -> str:
		i = "\n" + ("\t" * level)
		ii = i + "\t"

		return (i + "task {" + ii
			+ f"id : {self.id};{ii}"
			f"app : {self.app.name};{ii}"
			f"wcet : {self.wcet};{ii}"
			f"period : {self.period};{ii}"
			f"deadline : {self.deadline};{ii}"
			f"criticality : {int(self.criticality)};{ii}"
			f"jobs {{" + "".join(job.pformat(level + 2) for job in self.jobs) + ii + "}"
			+ (f"{ii}parent : {self.parent.id};{i}}}" if self.parent is not None else i + "}"))


@dataclass(eq=True)
@total_ordering
class App(Sequence, Reversible):
	"""An application.

	Attributes
	----------
	name : str
		The name of the Application.
	order : bool
		Whether or not the order of tasks is significant. Could also be obtained by `self.tasks[:-1].parent is not None`.
	tasks : list[Task]
		The tasks within the Application.
	"""

	name: str
	order: bool
	tasks: list[Task] = field(compare=False, default_factory=list)

	@cached_property
	def criticality(self: App) -> Criticality:
		"""Computes and caches the maximal criticality, [0; 4], within the tasks.
		We could also just return it from the first task in `tasks`.

		Parameters
		----------
		self
			The instance of `App`.

		Returns
		-------
		Criticality
			The maximal criticality within `self.tasks`, assuming a non-empty list of tasks.
		"""

		return max(self.tasks, key=lambda task: task.criticality).criticality

	@cached_property
	def workload(self: App) -> float:
		"""Computes and caches the workload of the tasks.

		Parameters
		----------
		self : App
			The instance of `App`.

		Returns
		-------
		float
			The workload of the app.
		"""

		return fsum(task.workload for task in self.tasks)

	def has_order_miss(self: App) -> bool:
		if len(self) < 2 or not self.order:
			return False

		for i in range(len(self.tasks[:-1])):
			if self[i + 1].jobs[-1].execution[-1].start < self[i].jobs[-1].execution[-1].stop:
				return True

		return False

	def __new__(cls: Type[App], name: str, order: bool) -> App:
		self = super().__new__(cls)  # Must explicitly create the new object
		# Aside from explicit construction and return, rest of __new__ is same as __init__
		self.name = name
		self.order = order
		self.tasks = []

		return self  # __new__ returns the new object

	def __getnewargs__(self: App) -> tuple[str, bool]:
		# Return the arguments that *must* be passed to __new__
		return (self.name, self.order)

	def __lt__(self: App, other: object) -> bool:
		if isinstance(other, App):
			return self.criticality < other.criticality
		else:
			return NotImplemented

	def __getitem__(self: App, key: int) -> Task:
		return self.tasks[key]

	def __contains__(self: App, item: object) -> bool:
		if isinstance(item, Task):
			return item.app is self and item in self.tasks
		else:
			return NotImplemented

	def __iter__(self: App) -> Iterator[Task]:
		return iter(self.tasks)

	def __reversed__(self: App) -> Iterator[Task]:
		return reversed(self.tasks)

	def __len__(self: App) -> int:
		return len(self.tasks)

	def __hash__(self: App) -> int:
		return hash(self.name)

	def pformat(self: App, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "app {" + i
		+ f"\tname : {self.name};{i}\tcriticality : {self.criticality};{i}\ttasks {{"
			+ "".join(task.pformat(level + 2) for task in self)
		+ i + "\t}" + i + "}")


class Graph(NamedTuple):
	"""A DAG containing apps and an hyperperiod.

	Attributes
	----------
	apps : SortedSet[App]
		The applications to schedule.
	hyperperiod : int
		The hyperperiod length for this `Graph`, the least common divisor of the periods of all tasks.
	"""

	apps: SortedSet[App]
	hyperperiod: int

	def max_criticality(self: Graph) -> Criticality:
		"""Computes and caches the maximal criticality within the apps.

		Parameters
		----------
		self
			The instance of `Graph`.

		Returns
		-------
		Criticality
			The maximal criticality within `self.apps`, assuming a non-empty list of applications.
		"""

		return max(self.apps, key=lambda app: app.criticality).criticality

	def pformat(self: Graph, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (f"{i}graph {{{i}\thyperperiod : {self.hyperperiod};"
			+ "".join(app.pformat(level + 1) for app in self.apps) + i + "}")
