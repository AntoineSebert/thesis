#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from __future__ import annotations


from collections.abc import Iterator, Reversible, Sequence, Set, Sized
from dataclasses import dataclass, field
from enum import IntEnum, unique
from functools import cached_property, total_ordering
from math import fsum
from typing import overload

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


@total_ordering
class Slice(Sized):
	"""Represents an execution slice of a task.

	Attributes
	----------
	job : Job
		The job the execution slice belongs to.
	start : int
		The start time of the execution slice.
	stop : int
		The stop time of the execution slice.
	"""

	job: Job
	start: int
	stop: int

	def __init__(self: Slice, job: Job, start: int, stop: int) -> None:
		if stop <= start:
			raise RuntimeError(f"Cannot instantiate Slice with {start=} and {stop=}.")
		elif start < job.exec_window.start or stop > job.exec_window.stop:
			raise RuntimeError(f"Cannot instantiate Slice with {start=} and {stop=}: does not match {job.exec_window}.")

		self.job = job
		self.start = start
		self.stop = stop

	# HASHABLE

	def __hash__(self: Slice) -> int:
		return hash(str(self.job) + str(self.start) + str(self.stop))

	# TOTAL ORDERING

	def __eq__(self: Slice, other: object) -> bool:
		"""
		self  |-----|
		other |-----|
		"""

		if isinstance(other, Slice):
			return self.start == other.start and self.stop == other.stop
		else:
			return NotImplemented

	def __gt__(self: Slice, other: object) -> bool:
		"""
		self          |-----|
		other |-----|
		"""

		if isinstance(other, Slice):
			return other.stop <= self.start
		else:
			return NotImplemented

	def __ge__(self: Slice, other: object) -> bool:
		"""
		self  |---------|
		other |-----|
		"""

		if isinstance(other, Slice):
			return other.start <= self.start and other.stop < self.stop
		else:
			return NotImplemented

	def __le__(self: Slice, other: object) -> bool:
		"""
		self  |---------|
		other     |-----|
		"""

		if isinstance(other, Slice):
			return self.start < other.start and self.stop <= other.stop
		else:
			return NotImplemented

	def __lt__(self: Slice, other: object) -> bool:
		"""
		self  |-----|
		other         |-----|
		"""

		if isinstance(other, Slice):
			return self.stop <= other.start
		else:
			return NotImplemented

	def intersect(self: Slice, other: object) -> bool:
		"""Checks if two slices intersect.
		https://stackoverflow.com/questions/3269434/whats-the-most-efficient-way-to-test-two-integer-ranges-for-overlap

		self  |-----|
		other    |-----|
		"""

		if isinstance(other, Slice) or isinstance(other, slice):
			return self.start < other.stop and other.start < self.stop
		else:
			return NotImplemented

	def __sub__(self: Slice, other: object) -> Slice:
		""" Assuming self > other
		self  |-----|
					|--|
		other          |-----|
		"""

		if isinstance(other, Slice):
			if other < self:
				return Slice(self.job, other.stop, self.start)
			elif self < other:
				return Slice(other.job, self.stop, other.start)
			else:
				return Slice(self.job, 0, 0)
		else:
			return NotImplemented

	# SIZED

	def __len__(self: Slice) -> int:
		return self.stop - self.start

	# STRING

	def __str__(self: Slice) -> str:
		return f"<{self.job.short()}:{self.start} - {self.stop}>"


@dataclass
@total_ordering
class Job(Set, Reversible):
	"""Represents an instance of a task.

	Attributes
	----------
	task : Task
		The task the job belongs to.
	sched_window : slice
		The window scheduling time, representing (activation_time, activation_time + deadline).
	exec_window : slice
		The window execution time, taking into account the offset and local deadline.
	execution : list[Slice]
		Set of execution slices.
	"""

	task: Task
	sched_window: slice
	exec_window: slice
	execution: list[Slice] = field(default_factory=list)

	def duration(self: Job) -> int:
		"""Computes and caches the duration of the slice.

		Parameters
		----------
		self : Job
			The instance of `Job`.

		Returns
		-------
		int
			The duration of all the execution slices of the job.
		"""

		return sum((len(_slice) for _slice in self), start=0)

	def offset(self: Job) -> int:
		"""Computes and returns the offset of the job.

		Parameters
		----------
		self : Job
			The instance of `Job`.

		Returns
		-------
		int
			The offset of the job.
		"""

		return self.exec_window.start - self.sched_window.start

	@cached_property
	def local_deadline(self: Job) -> int:
		"""Computes and returns the local deadline of the job.

		Parameters
		----------
		self : Job
			The instance of `Job`.

		Returns
		-------
		int
			The local deadline of the job.
		"""

		return self.exec_window.stop - self.sched_window.stop

	def has_execution_miss(self: Job) -> bool:
		"""Checks if all the execution slices are within the scheduling window.

		Parameters
		----------
		self : Job
			The instance of `Job`.

		Returns
		-------
		bool
			Returns `True` if at least one execution slice is out of the scheduling window, or `False` otherwise.
		"""

		return self.__len__() == 0 or self.has_deadline_miss() or self.has_offset_miss() or self.has_wcet_miss()

	def has_deadline_miss(self: Job) -> bool:
		"""Checks if the deadline of the job is missed.

		Parameters
		----------
		self : Job
			The instance of `Job`.

		Returns
		-------
		bool
			Returns `True` if the last execution slice ends after the scheduling window, or `False` otherwise.
		"""

		#print(self.execution[-1].stop, self.exec_window.stop)

		return self.execution[-1].stop > self.exec_window.stop

	def has_offset_miss(self: Job) -> bool:
		"""Checks if the offset of the job is missed.

		Parameters
		----------
		self : Job
			The instance of `Job`.

		Returns
		-------
		bool
			Returns `True` if the last execution slice starts before the scheduling window, or `False` otherwise.
		"""

		return self.execution[0].start < self.exec_window.start

	def has_wcet_miss(self: Job) -> bool:
		return self.duration() != self.task.wcet

	def short(self: Job) -> str:
		"""A short description of a job.

		Parameters
		----------
		self : Job
			The instance of `Job`.

		Returns
		-------
		str
			The short description.
		"""

		return f"{self.task.short()} [{self.sched_window.start} - {self.sched_window.stop}][{self.exec_window.start} - {self.exec_window.stop}]"

	def pformat(self: Job, level: int = 0) -> str:
		"""A complete description of a job.

		Parameters
		----------
		self : Job
			The instance of `Job`.
		level : int, optional
			The indentation level (default: 0).

		Returns
		-------
		str
			The complete description.
		"""

		i = "\n" + ("\t" * level)
		ii = i + "\t"

		return (f"{i}job {{{ii}"
			f"task : {self.task.app.name} / {self.task.id};{ii}"
			f"window : {self.sched_window} / {self.exec_window} / {self.duration()};{ii}"
			f"execution {{" + "".join(f"{ii}\t{_slice.start} - {_slice.stop};" for _slice in self) + ii + "}" + i + "}")

	# HASHABLE

	def __hash__(self: Job) -> int:
		return hash(str(self.task) + str(self.sched_window))

	# TOTAL ORDERING

	def __eq__(self: Job, other: object) -> bool:
		if isinstance(other, Job):
			return self.task == other.task and self.sched_window == other.sched_window
		else:
			return NotImplemented

	def __lt__(self: Job, other: object) -> bool:
		if isinstance(other, Job):
			return self.exec_window.stop < other.exec_window.stop
		else:
			return NotImplemented

	# SET

	def __contains__(self: Job, item: object) -> bool:
		if isinstance(item, slice):
			return self.execution.__contains__(item)
		else:
			return NotImplemented

	def __len__(self: Job) -> int:
		return self.execution.__len__()

	# REVERSIBLE

	def __reversed__(self: Job) -> Iterator[Slice]:
		return self.execution.__reversed__()

	# ITERABLE

	def __iter__(self: Job) -> Iterator[Slice]:
		return self.execution.__iter__()

	# DEEPCOPY

	def __deepcopy__(self: Job, memo: dict[int, object]) -> Job:
		cls = self.__class__
		result = cls.__new__(cls)
		memo[id(self)] = result

		result.task = self.task
		result.sched_window = self.sched_window
		result.exec_window = self.exec_window
		result.execution = []

		return result


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
	parent : Task
		A list of tasks to be completed before starting.
	jobs : list[Job]
		A set of n instances of the task, with n = int(wcet / hyperperiod).
	"""

	id: int
	app: App
	wcet: int
	period: int
	deadline: int
	criticality: Criticality
	parent: Task
	jobs: list[Job] = field(default_factory=list)

	@cached_property
	def workload(self: Task) -> float:
		"""Computes and caches the workload of the task.

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
		"""A short description of a task.

		Parameters
		----------
		self : Task
			The instance of `Task`.

		Returns
		-------
		str
			The short description.
		"""

		return f"{self.app.name} / {self.id}"

	def pformat(self: Task, level: int = 0) -> str:
		"""A complete description of a task.

		Parameters
		----------
		self : Task
			The instance of `Task`.
		level : int, optional
			The indentation level (default: 0).

		Returns
		-------
		str
			The complete description.
		"""

		i = "\n" + ("\t" * level)
		ii = i + "\t"

		return (i + "task {" + ii
			+ f"id : {self.id};{ii}"
			f"app : {self.app.name};{ii}"
			f"wcet : {self.wcet};{ii}"
			f"period : {self.period};{ii}"
			f"deadline : {self.deadline};{ii}"
			f"criticality : {int(self.criticality)};{ii}"
			f"jobs {{" + "".join(job.pformat(level + 2) for job in self) + ii + "}"
			+ (f"{ii}parent : {self.parent.id};{i}}}" if self.parent is not None else i + "}"))

	# HASHABLE

	def __hash__(self: Task) -> int:
		return hash(str(self.id) + self.app.name)

	# TOTAL ORDERING

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

	# SET

	def __contains__(self: Task, item: object) -> bool:
		if isinstance(item, Job):
			return self.jobs.__contains__(item)
		else:
			return NotImplemented

	def __len__(self: Task) -> int:
		return self.jobs.__len__()

	# REVERSIBLE

	def __reversed__(self: Task) -> Iterator[Job]:
		return self.jobs.__reversed__()

	# ITERABLE

	def __iter__(self: Task) -> Iterator[Job]:
		return self.jobs.__iter__()


@dataclass
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
	tasks: list[Task] = field(default_factory=list)

	@cached_property
	def criticality(self: App) -> Criticality:
		"""Computes and caches the maximal criticality, [0; 4], within the tasks.
		We could also just return it from the first task in `tasks`.

		Parameters
		----------
		self : App
			The instance of `App`.

		Returns
		-------
		Criticality
			The maximal criticality within `self.tasks`, assuming a non-empty list of tasks.
		"""

		return max(self, key=lambda task: task.criticality).criticality

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

		return fsum(task.workload for task in self)

	def pformat(self: App, level: int = 0) -> str:
		"""A complete description of an application.

		Parameters
		----------
		self : App
			The instance of `Task`.
		level : int, optional
			The indentation level (default: 0).

		Returns
		-------
		str
			The complete description.
		"""

		i = "\n" + ("\t" * level)

		return (i + "app {" + i
		+ f"\tname : {self.name};{i}\tcriticality : {self.criticality};{i}\ttasks {{"
			+ "".join(task.pformat(level + 2) for task in self)
		+ i + "\t}" + i + "}")

	# HASHABLE

	def __hash__(self: App) -> int:
		return hash(self.name)

	# TOTAL ORDERING

	def __eq__(self: App, other: object) -> bool:
		if isinstance(other, App):
			return self.name == other.name
		else:
			return NotImplemented

	def __lt__(self: App, other: object) -> bool:
		if isinstance(other, App):
			return self.criticality < other.criticality
		else:
			return NotImplemented

	# SEQUENCE

	def __contains__(self: App, item: object) -> bool:
		if isinstance(item, Task):
			return self.tasks.__contains__(item)
		else:
			return NotImplemented

	@overload
	def __getitem__(self: App, key: int) -> Task:
		return self.tasks.__getitem__(key)

	@overload
	def __getitem__(self: App, key: slice) -> list[Task]:
		return self.tasks.__getitem__(key)

	def __getitem__(self, key):
		return self.tasks.__getitem__(key)

	def __len__(self: App) -> int:
		return self.tasks.__len__()

	# REVERSIBLE

	def __reversed__(self: App) -> Iterator[Task]:
		return self.tasks.__reversed__()

	# ITERABLE

	def __iter__(self: App) -> Iterator[Task]:
		return self.tasks.__iter__()


@dataclass
class Graph(Set, Reversible):
	"""A DAG containing apps and an hyperperiod.

	Attributes
	----------
	apps : list[App]
		The applications to schedule.
	hyperperiod : int
		The hyperperiod length for this `Graph`, the least common divisor of the periods of all tasks.
	"""

	apps: list[App]
	hyperperiod: int

	@cached_property
	def max_criticality(self: Graph) -> Criticality:
		"""Computes and caches the maximal criticality within the apps.

		Parameters
		----------
		self : Graph
			The instance of `Graph`.

		Returns
		-------
		Criticality
			The maximal criticality within `self.apps`, assuming a non-empty list of applications.
		"""

		return max(self, key=lambda app: app.criticality).criticality

	def pformat(self: Graph, level: int = 0) -> str:
		"""A complete description of a graph.

		Parameters
		----------
		self : Graph
			The instance of `Graph`.
		level : int, optional
			The indentation level (default: 0).

		Returns
		-------
		str
			The complete description.
		"""

		i = "\n" + ("\t" * level)

		return f"{i}graph {{{i}\thyperperiod : {self.hyperperiod};" + "".join(app.pformat(level + 1) for app in self) + i + "}"

	# SET

	def __contains__(self: Graph, item: object) -> bool:
		if isinstance(item, App):
			return self.apps.__contains__(item)
		else:
			return NotImplemented

	def __len__(self: Graph) -> int:
		return self.apps.__len__()

	# REVERSIBLE

	def __reversed__(self: Graph) -> Iterator[App]:
		return self.apps.__reversed__()

	# ITERABLE

	def __iter__(self: Graph) -> Iterator[App]:
		return self.apps.__iter__()
