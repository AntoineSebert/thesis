#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from __future__ import annotations


from collections.abc import Iterator, Reversible, Set
from dataclasses import dataclass, field
from enum import IntEnum, unique
from functools import cached_property, total_ordering
from math import fsum
from typing import NamedTuple

from defusedxml import ElementTree  # type: ignore


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


@dataclass(order=True)
class Task:
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
	child : Task
		A list of tasks to be completed before starting.
	"""

	id: int = field(compare=False)
	app: App = field(compare=False)
	wcet: int = field(compare=False)
	period: int = field(compare=False)
	# n_slots cached_property : hyperperiod / period, list[exec_window]
	deadline: int = field(compare=False)
	criticality: Criticality
	child: Task = field(compare=False)

	def __init__(self: Task, node: ElementTree, app: App) -> None:
		self.id = int(node.get("Id"))
		self.app = app
		self.wcet = int(node.get("WCET"))
		self.period = int(node.find("Period").get("Value"))
		self.deadline = int(node.get("Deadline"))
		self.criticality = Criticality(int(node.get("CIL")))

	def __hash__(self: Task) -> int:
		return hash(str(self.id) + self.app.name)

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

	def pformat(self: Task, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "task {" + i
			+ f"\tid : {self.id};{i}"
			f"\tapp : {self.app.name};{i}"
			f"\twcet : {self.wcet};{i}"
			f"\tperiod : {self.period};{i}"
			f"\tdeadline : {self.deadline};{i}"
			f"\tcriticality : {int(self.criticality)};{i}"
			+ (f"\tchild : {self.child.id};{i}}}" if self.child is not None else "}"))


@dataclass(eq=True)
@total_ordering
class App(Set, Reversible):
	"""An application. Mutable.

	Attributes
	----------
	name : str
		The name of the Application.
	tasks : set[Task]
		The tasks within the Application.
	"""

	name: str
	tasks: set[Task] = field(compare=False)  # non-deterministic order

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

	def __lt__(self: App, other: object) -> bool:
		if isinstance(other, App):
			return self.criticality < other.criticality
		else:
			return NotImplemented

	def __contains__(self: App, item: object) -> bool:
		if isinstance(item, Task):
			return item.app is self and item in self.tasks
		else:
			return NotImplemented

	def __iter__(self: App) -> Iterator[Task]:
		return iter(self.tasks)

	def __reversed__(self: App) -> Iterator[Task]:
		for task in self.tasks[::-1]:
			yield task

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
