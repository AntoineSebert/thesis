#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from __future__ import annotations
from enum import IntEnum, unique
from dataclasses import dataclass, field
from fractions import Fraction
from json import JSONEncoder
from pathlib import Path
from queue import PriorityQueue
from typing import Any, List, NamedTuple, Optional, Dict
from weakref import ReferenceType


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


@dataclass
class Processor:
	"""Represents a processor. Mutable.

	Attributes
	----------
	id : int
		The processor within an `Architecture`.
	cores : List[Core]
		The List containing the `Core` objects within the Processor.
	"""

	id: int
	cores: List[Core]


"""An List of `Processor` representing an `Architecture`."""
Architecture = List[Processor]


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


@dataclass
class App:
	"""An application. Mutable.

	Attributes
	----------
	name : str
		The name of the Application.
	tasks : List[Task]
		The list of tasks within the Application.
	"""

	name: str
	tasks: List[Task]


"""An list of `App` representing an `Graph`."""
Graph = List[App]


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
	mapping : Dict[Task, Core]
		A mapping between tasks and cores.
	"""

	config: Configuration
	arch: Architecture
	hyperperiod: int
	score: int
	mapping: Dict[Task, Core]


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
