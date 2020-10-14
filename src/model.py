#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, unique
from functools import cached_property
from json import JSONEncoder
from pathlib import Path
from queue import PriorityQueue
from typing import Any, Callable, NamedTuple, Union
from weakref import ReferenceType, ref

from defusedxml import ElementTree


@unique
class Criticality(IntEnum):
	"""Task criticality level

	sta_1: null
	sta_2: bounded jitter
	sta_3: 0 jitter
	sta_4: 0 jitter and minimal completion time
	"""

	sta_1 = 1
	sta_2 = 2
	sta_3 = 3
	sta_4 = 4


class Core(NamedTuple):
	"""Represents a core. Immutable.

	Attributes
	----------
	id : int
		The core id within a `Processor`.
	processor : ReferenceType[Processor]
		The processor this core belongs to.
	macrotick : int
		The macrotick of the core.
	"""

	id: int
	processor: ReferenceType[Processor]
	macrotick: int

	def pformat(self: Core, level: int = 0) -> str:
		return ("\t" * level) + f"core {{ id : {self.id}; macrotick : {self.macrotick}; }}"


@dataclass
class Processor:
	"""Represents a processor. Mutable.

	Attributes
	----------
	id : int
		The processor within an `Architecture`.
	cores : list[Core]
		The list containing the `Core` objects within the Processor.
	"""

	id: int
	cores: list[Core]

	def pformat(self: Processor, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "cpu {" + i
		+ f"\tid : {self.id};\n"
		+ ("\n").join([core.pformat(level + 1) for core in self.cores])
		+ i + "}")


"""An list of `Processor` representing an `Architecture`."""
Architecture = list[Processor]


@dataclass
class Slice:
	"""Named tuple representing an execution slice of a task.

	Attributes
	----------
	task : int
		The reference to the task the slice belongs to.
	core : ReferenceType[Core]
		The reference to the core the slice is scheduled on.
	start : int
		The start time of the slice.
	stop : int
		The stop time of the slice.
	"""

	task: ReferenceType[Task]
	core: ReferenceType[Core]
	start: int
	stop: int


@dataclass(order=True)
class Task:
	"""Represents a task.

	Attributes
	----------
	id : int
		The node id within a `Chain`.
	app : ReferenceType[App]
		The App to which the task belongs to.
	wcet : int
		The WCET of the node. Cannot be `0`.
	period : int
		The period of the node. Cannot be `0`.
	deadline : int
		The deadline of the node.
	offset : Optional[int]
		The start offset of the node.
	cpu : ReferenceType[Processor]
		A `Processor` the node is scheduled on. Cannot be None.
	criticality : Criticality
		The criticality level, [1; 3].
	child : List[ReferenceType[Task]]
		A list of tasks to be completed before starting.
	"""

	id: int = field(compare=False)
	app: ReferenceType[App] = field(compare=False)
	wcet: int = field(compare=False)
	period: int = field(compare=False)
	deadline: int = field(compare=False)
	offset: Optional[int] = field(compare=False)
	cpu: ReferenceType[Processor] = field(compare=False)
	criticality: Criticality = field(compare=False)
	child: ReferenceType[Task] = field(compare=False, default=None)

	def __init__(self: Task, node: ElementTree, app: App, cpu: Processor) -> Task:
		self.id = int(node.get("Id"))
		self.app = ref(app)
		self.wcet = int(node.get("WCET"))
		self.period = int(node.find("Period").get("Value"))
		self.deadline = int(node.get("Deadline"))
		self.offset = int(node.get("EarliestActivation")) if node.get("EarliestActivation") is not None else None
		self.cpu = ref(cpu)
		self.criticality = Criticality(int(node.get("CIL")))

	def pformat(self: Task, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "task {" + i
			+ f"\tid : {self.id};{i}"
			+ f"\tapp : {self.app().name};{i}"
			+ f"\twcet : {self.wcet};{i}"
			+ f"\tperiod : {self.period};{i}"
			+ f"\tdeadline : {self.deadline};{i}"
			+ (f"\toffset : {self.offset};{i}" if self.offset is not None else "")
			+ f"\tcpu : {self.cpu().id};{i}"
			+ f"\tcriticality : {int(self.criticality)};{i}"
			+ (f"\tchild : {self.child().id};" if self.child is not None else "")
		+ i + "}")

	@cached_property
	def score(self:Task, policy) -> int:
		return 0


@dataclass
class App:
	"""An application. Mutable.

	Attributes
	----------
	name : str
		The name of the Application.
	tasks : list[Task]
		The list of tasks within the Application.
	"""

	name: str
	tasks: list[Task]

	def pformat(self: App, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "app {" + i
			+ f"\tname : {self.name};{i}"
			+ f"\ttasks {{" +
				("").join([task.pformat(level + 2) for task in self.tasks])
			+ i + "\t}"
		+ i + "}")
class Graph(NamedTuple):
	apps: list[App]


		return (f"{i}graph {{{i}\thyperperiod : {self.hyperperiod};"
			+ "".join(app.pformat(level + 1) for app in self.apps) + i + "}")


class FilepathPair(NamedTuple):
	"""Holds a `FilepathPair` to a `*.tsk` and a `*.cfg` file, representing a test case. Immutable.

	Attributes
	----------
	tsk : Path
		A `Path` to a `*.tsk` file.
	cfg : Path
		A `Path` to a `*.cfg` file.
	"""

	tsk: Path
	cfg: Path


class Configuration(NamedTuple):
	"""Binds a `FilepathPair` to a constraint level and a scheduling policy. Immutable.

	Attributes
	----------
	filepaths : FilepathPair
		A `FilepathPair` from which a `Problem` will be generated.
	constraint_level : int
		A constraint level that adjust which constraints will be met.
	policy : str
		A scheduling policy.
	"""

	filepaths: FilepathPair
	constraint_level: int
	policy: str

	def pformat(self: Configuration, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "configuration {" + i
			+ f"\tcases : {self.filepaths};{i}\tconstraint level : {self.constraint_level};{i}\tpolicy : {self.policy};"
		+ i + "}")


class Problem(NamedTuple):
	"""A problem holding a `FilepathPair`, a `Graph`, an architecture.

	Attributes
	----------
	config : Configuration
		A configuration for a scheduling problem.
	arch : Architecture
		An `Architecture` containing a sequence of `Processor`.
	graph : Graph
		A `Graph` containing task sequences.
	"""

	config: Configuration
	arch: Architecture
	graph: Graph


"""A mapping of cores to slices, representing the inital mapping."""
Mapping = dict[ReferenceType[Core], list[ReferenceType[Slice]]]


@dataclass
class Solution:
	"""A solution holding an hyperperiod as `int`, and an architecture as Architecture (should be: `ref(Architecture)`).

	Attributes
	----------
	config: Configuration
		A configuration for a scheduling problem.
	arch : Architecture
		An `Architecture` containing a sequence of `Processor`.
	hyperperiod : int
		The hyperperiod length for this `Solution`.
	score : int
		The score of a Solution regarding an objective function.
	mapping : Mapping
		A mapping between cores and tasks.
	"""

	config: Configuration
	arch: Architecture
	hyperperiod: int
	score: int
	mapping: Mapping


class PriorityQueueEncoder(JSONEncoder):
	"""An encoder dedicated to parse `PriorityQueue` objects into JSON.

	Methods
	-------
	default(obj)
		Returns a list containing the size of the `PriorityQueue` and a boolean whether it is empty or not.
	"""

	def default(self: JSONEncoder, obj: Any) -> Any:
		if isinstance(obj, PriorityQueue):
			return [obj.qsize(), obj.empty()]
		# Let the base class default method raise the TypeError
		return JSONEncoder.default(self, obj)
